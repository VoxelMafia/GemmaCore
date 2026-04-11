"""
core/agent_core.py — The deterministic cognitive loop.

Loop structure (executed once per iteration):
    perception()
    update_state()
    reasoning()
    planning()
    action()
    reflection()
    memory_update()

Each phase is explicit, traceable, and logged.
"""
from __future__ import annotations
import threading
import time
import random
import json
import re
import uuid
from typing import Any, Optional
from ai.prompts import planner_prompt
from ai.prompts import research_gaps_prompt
from config.settings import settings
from core.state import AgentState, AgentStatus, ActionRecord, Goal
from core.personality import PersonalityEngine
from core.planner import Planner
from memory.short_term import ShortTermMemory
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.long_term import LongTermMemory
from llm.interface import LLMInterface
from skills.file_ops import FileOpsSkill
from skills.registry import SkillRegistry
from observability.logger import get_logger
from observability.trace import Tracer

logger = get_logger(__name__)


class AgentCore:
    """
    The cognitive runtime. Owns state, memory, personality, and the loop thread.
    The UI / CLI should call start() / stop() only.
    """

    def __init__(self, ui=None):
        self.ui = ui
        self.state = AgentState(session_id=str(uuid.uuid4()))
        self.personality = PersonalityEngine(self.state.personality)
        self.tracer = Tracer(self.state.session_id)
        self.planner = Planner(self.state, self.personality, self.tracer)
        self.llm: Optional[LLMInterface] = None
        self.skills: Optional[SkillRegistry] = None

        # Memory layers
        self.stm = ShortTermMemory(capacity=settings.memory.short_term_capacity)
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.ltm = LongTermMemory(path=settings.memory.path,
                                  enabled=settings.memory.long_term_enabled)

        self._thread: Optional[threading.Thread] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_goal(self, goal_input: Any) -> None:
        """Accept dict, string, or list; normalize into Goal object."""
        if isinstance(goal_input, dict):
            pd = goal_input.get("primary_domain", "")
            idom = goal_input.get("intersection_domain", "")
            desc = f"{pd} AND {idom}".strip(" AND") if idom else pd
            goal = Goal(description=desc, primary_domain=pd, intersection_domain=idom)
        elif isinstance(goal_input, (list, tuple)) and len(goal_input) >= 2:
            goal = Goal(description=f"{goal_input[0]} AND {goal_input[1]}",
                        primary_domain=str(goal_input[0]),
                        intersection_domain=str(goal_input[1]))
        else:
            goal = Goal(description=str(goal_input), primary_domain=str(goal_input))

        self.state.goals = [goal]
        self.state.current_goal = goal
        self.state.iteration = 0
        self.state.thesis_outline = []
        self.state.attempted_urls = []
        self.state.source_map = {}
        self.state.consecutive_failures = 0
        logger.info(f"[GOAL] Set: {goal.description}")

    def start(self, goal_input: Any = None, auto_approve: bool = False) -> None:
        if goal_input is not None:
            self.set_goal(goal_input)

        # Initialize subsystems lazily here (after goal is known)
        from llm.gemma_provider import GemmaProvider
        self.llm = GemmaProvider()

        self.skills = SkillRegistry(agent=self)
        self.skills.load_defaults()

        if auto_approve and hasattr(self, "approval"):
            self.approval.set_auto_approve(True)

        # Clear session memory
        self.stm.clear()
        self.episodic.clear_session()
        self.semantic.clear_session()

        self.state.running = True
        self.state.set_status(AgentStatus.IDLE)

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"[SYSTEM] Agent started — session {self.state.session_id}")

    def stop(self) -> None:
        self.state.running = False
        self.state.set_status(AgentStatus.STOPPED)
        logger.info("[SYSTEM] Agent stop requested.")
        # Clean up browser skill if loaded
        browser = self.skills.get("browser") if self.skills else None
        if browser and hasattr(browser, "stop"):
            try:
                browser.stop()
            except Exception:
                pass

    # ── Private: Loop ─────────────────────────────────────────────────────────

    def _run(self) -> None:
        try:
            # Initialize connection to LLM and verify Skills
            self._phase_init()

            for idx, chapter in enumerate(self.state.thesis_outline):
                if not self.state.running:
                    break
                
                # ── KNOWLEDGE BRIDGE (Prevents Chapter 2 Amnesia) ──
                # 1. Extract viable points before clearing the noisy chapter session
                summary_text = self.semantic.retrieve("Key findings, methodologies, and DOIs", k=5)
                
                # 2. Strategic Memory Clear (Hygiene)
                self.stm.clear()
                self.semantic.clear_session() 
                
                # ── NEW: KNOWLEDGE BRIDGE RE-INDEXING ──
                # Iterate through existing sources and re-inject them into the new session
                if self.state.source_map:
                    # 1. Sort by score so we only bridge the absolute best evidence
                    sorted_sources = sorted(
                        self.state.source_map.values(), 
                        key=lambda x: x.get("score", 0), 
                        reverse=True
                    )
                    
                    # 2. Limit the bridge to the Top 3 most relevant sources to save VRAM
                    top_sources = sorted_sources[:3]
                    
                    logger.info(f"[MEMORY] Bridging top {len(top_sources)} sources for Chapter Context.")
                    
                    for data in top_sources:
                        # 3. Add a 'bridge' tag so the LLM knows this is historical data
                        # Use a more compressed format to save tokens
                        bridge_content = (
                            f"HISTORICAL_CONTEXT: {data['content'][:300]}... "
                            f"Ref: {data.get('anchor', 'SOURCE')} DOI: {data.get('doi')}"
                        )
                        self.semantic.store(bridge_content)

                logger.info(f"[SYSTEM] Transitioning to {chapter}. Viable points retained.")
                # 2. Reset chapter-specific state
                self.state.attempted_urls = [] # Clear this to allow specific searches for the new chapter
                
                self._emit(f"Chapter {idx + 1}/{len(self.state.thesis_outline)}: {chapter}")
                self.state.current_chapter_index = idx
                self.state.current_chapter_title = chapter
                self.state.iteration = 0
                self.state.current_sub_goal = f"Deconstructing {chapter}"
                self.state.current_chapter_index = idx
                # ── ITERATION LOOP ──
                while self.state.iteration < settings.agent.max_iterations and self.state.running:
                    # ── RIGOR-LOOP BREAKER ──
                    # Force progress if we are nearing the iteration limit
                    if self.state.iteration >= (settings.agent.max_iterations - 1):
                        self.state.push_short_term(
                            "SYSTEM NOTICE: Research capacity reached. You MUST now synthesize "
                            "findings and execute COMMAND: WRITE for this chapter."
                        )
                    
                    self._loop_iteration() 
                    
                    self.state.iteration += 1
                    time.sleep(random.uniform(0.4, 1.0))

                # Synthesis phase for the completed chapter
                # Before calling _phase_finalize_chapter():
                    if len([s for s in self.state.source_map.values() if s.get('chapter') == self.state.current_chapter_title]) < 1:
                        self._emit("⚠️ Warning: Fewer than 1 source found for this chapter. The synthesis may be weak.")
                self._phase_finalize_chapter()

            # ── NEW: MERGE AND CLEAN THESIS ──
            topic_folder = FileOpsSkill._slugify(self.state.current_goal.description)
            merge_result = self.skills.get("file_ops").execute({
                "action": "merge_and_clean",
                "folder": topic_folder,
                "title": f"Complete_Thesis_{topic_folder}"
            })
            logger.info(f"[SYSTEM] Thesis compilation: {merge_result}")

            self._emit("✅ Full Thesis Synthesis Complete.")
            self.state.set_status(AgentStatus.IDLE)

        except Exception as exc:
            self.state.last_error = str(exc)
            self.state.set_status(AgentStatus.ERROR)
            logger.error(f"[SYSTEM] Fatal loop error: {exc}", exc_info=True)
            self._emit(f"Fatal error: {exc}")
        finally:
            self.stop()

    def _loop_iteration(self) -> None:
        """One full cognitive cycle."""
        s = self.state

        # ── 1. PERCEPTION ────────────────────────────────────────────────────
        s.set_status(AgentStatus.PERCEIVING)
        perception = self._phase_perception()
        self.tracer.record("PERCEPTION", {"summary": perception[:300]})
        logger.info(f"[PERCEPTION] {perception[:120]}")

        # ── 2. STATE UPDATE ──────────────────────────────────────────────────
        s.current_context = perception

        # ── 3. REASONING ─────────────────────────────────────────────────────
        s.set_status(AgentStatus.REASONING)
        raw_plan = self._phase_reasoning(perception)
        s.last_plan = raw_plan
        self.tracer.record("THOUGHT", {"plan_excerpt": raw_plan[:300]})
        logger.info(f"[THOUGHT] {raw_plan[:120]}")

        # ── 4. PLANNING ──────────────────────────────────────────────────────
        s.set_status(AgentStatus.PLANNING)
        chosen = self.planner.interpret(raw_plan)
        sub_goal = self.planner.extract_sub_goal(raw_plan)
        if sub_goal:
            s.current_sub_goal = sub_goal
        logger.info(f"[PLAN] Action={chosen.action_type} Skill={chosen.skill_name} Confidence={chosen.confidence:.2f}")

        # ── 5. ACTION ────────────────────────────────────────────────────────
        s.set_status(AgentStatus.ACTING)
        if chosen.requires_approval and hasattr(self, "approval") and self.approval:
            s.set_status(AgentStatus.AWAITING_APPROVAL)
            self._emit(f"⏳ Awaiting approval: {s.current_sub_goal[:60]}…")
            if not self.approval.request(raw_plan):
                logger.info("[ACTION] User rejected plan.")
                return

        # EXECUTION: Call the action phase
        raw_result = self._phase_action(chosen)
        
        # SAFETY FIX: Ensure result is always a string to prevent 'NoneType' errors during slicing
        result = str(raw_result) if raw_result is not None else "Action returned no output."
        
        s.last_action_result = result
        self.tracer.record("ACTION", {
            "type": chosen.action_type,
            "payload": str(chosen.payload)[:120],
            "result_excerpt": result[:200], # Safe now because result is a string
        })
        logger.info(f"[ACTION] {chosen.action_type} → {result[:80]}")

        # ── 6. REFLECTION ────────────────────────────────────────────────────
        s.set_status(AgentStatus.REFLECTING)
        reflection = self._phase_reflection(raw_plan, result)
        s.last_reflection = reflection
        self.tracer.record("RESULT", {"reflection_excerpt": reflection[:300]})
        logger.info(f"[RESULT] {reflection}")
        
        # ── 7. MEMORY UPDATE ─────────────────────────────────────────────────
        s.set_status(AgentStatus.UPDATING_MEMORY)
        self._phase_memory_update(reflection, chosen)
        self.tracer.record("REFLECTION", {"stored": True})
        logger.info("[REFLECTION] Memory updated.")

        # Personality evolution and Failure Tracking
        success = len(result) > 10 and "error" not in result.lower()
        self.personality.update_from_outcome("curiosity", success)
        self.personality.update_from_outcome("persistence", success)
        self.personality.apply_to_state(s)

        if not success:
            s.consecutive_failures += 1
        else:
            s.consecutive_failures = 0

        # Record action in state
        s.add_action(ActionRecord(
            step=s.iteration,
            action_type=chosen.action_type,
            input_summary=str(chosen.payload)[:120],
            output_summary=result[:120],
            skill_used=chosen.skill_name,
            success=success,
        ))

    # ── Private: Phases ────────────────────────────────────────────────────────

    def _phase_init(self) -> None:
        """Generate research gap and thesis outline before the main loop."""
        s = self.state
        g = s.current_goal

        self._emit(f"🔬 Initiating research scan: {g.description}")
        topic_folder = FileOpsSkill._slugify(g.description)
        self.skills.get("file_ops")._write(f"{topic_folder}/.placeholder", "Research started.")
        # Research gap → thesis goal
        if not g.description.strip().lower() or g.description.lower() == "autonomous":
            prompt = research_gaps_prompt(g.primary_domain or "Emerging Tech",
                                          g.intersection_domain or "Sustainability")
            raw = self.llm.complete(prompt)
            suggestions = self._safe_json_parse(raw, ["Adaptive Systems Gap"])
            g.description = self._clean_title(suggestions[0])
            self._emit(f"💡 Selected research gap: {g.description}")

        # Thesis outline
        outline_prompt = (
            f"Create a formal 5-chapter thesis outline for: {g.description}. "
            "Structure: Introduction, Literature Critique, Methodology, Empirical Synthesis, Conclusion. "
            "Return ONLY a JSON list of strings."
        )
        raw_outline = self._safe_json_parse(
            self.llm.complete(outline_prompt),
            ["Introduction", "Literature Critique", "Methodology", "Synthesis", "Conclusion"]
        )
        s.thesis_outline = [self._clean_title(t) for t in raw_outline]
        self._emit(f"📋 Outline: {' → '.join(s.thesis_outline)}")

    def _phase_perception(self) -> str:
        """Gather current context: memory + source map + sub-goal."""
        s = self.state
        
        # 1. Prioritize Short Term Memory (Crucial to break loops)
        stm_context = "\n".join(self.stm.recent(n=3))
        safe_stm = stm_context[:800] # Guarantee 800 chars for STM
        
        # 2. Fetch Semantic Memory
        mem_context = str(self.semantic.retrieve(s.current_sub_goal, k=4))[:600]
        
        # 3. Fetch Sources (Truncate to whatever space is left)
        high_rigor = [
            f"SOURCE: {src['content'][:200]}" # Tighter crop on sources
            for src in s.source_map.values() if src.get("score", 0) >= 0.6
        ]
        safe_sources = "\n".join(high_rigor)[:1000] 

        context = (
            f"GOAL: {s.active_goal_str()}\n"
            f"CHAPTER: {s.current_chapter_title}\n"
            f"SUB_GOAL: {s.current_sub_goal}\n"
            f"SHORT_TERM (Recent Actions):\n{safe_stm}\n"
            f"RECENT_MEMORY:\n{mem_context}\n"
            f"VERIFIED_SOURCES:\n{safe_sources}"
        )
        return context
    
    def _phase_reasoning(self, perception: str) -> str:
        """Call LLM with personality-biased planner prompt."""
        from ai.prompts import planner_prompt
        prefix = self.personality.reasoning_prefix()
        
        # Ensure current_sub_goal is never None for semantic search
        query = self.state.current_sub_goal or "Next research steps"
        context = self.semantic.retrieve(query, k=6)
        
        augmented = f"[PERSONALITY BIAS]: {prefix}\n\n{perception}"

        return self.llm.complete(planner_prompt(augmented, context))
    
    def _phase_action(self, chosen) -> str:
        s = self.state

        if chosen.action_type == "SEARCH":
            academic = self.skills.get("academic")
            search_key = str(chosen.payload.get("query", chosen.payload))
            
            # FIX 1: Allow re-searching if we are in a new chapter context
            if search_key in s.attempted_urls:
                logger.info(f"[ACTION] Skipping duplicate search: {search_key[:60]}")
                return f"SYSTEM: Query '{search_key}' already attempted. Try more specific keywords like 'architecture', 'validation', or 'hyperparameters'."
            
            s.attempted_urls.append(search_key)
            papers = academic.execute(chosen.payload)
            
            if isinstance(papers, list) and papers:
                parts = []
                relevant_count = 0
                
                for p in papers:
                    purl = p.get("url") or f"doi:{p.get('doi', 'unknown')}"
                    
                    # FIX 2: Check relevance and title before storing
                    analysis = self._grade_evidence(purl, p["abstract"], is_api=True)
                    
                    # Add metadata to the analysis for the writer to use
                    analysis["title"] = p.get("title")
                    analysis["anchor"] = p.get("anchor")
                    analysis["citation"] = p.get("citation_line")
                    analysis["chapter"] = s.current_chapter_title # Tag by chapter!
                    
                    s.source_map[purl] = analysis
                    
                    if analysis["is_relevant"]:
                        relevant_count += 1
                        # FIX 3: Smaller snippets for the loop, keep full data in source_map
                        parts.append(f"FOUND {p['anchor']}: {p['title']}\nAbstract: {p['abstract'][:400]}...")
                
                self._emit(f"Search successful: Found {relevant_count} relevant papers out of {len(papers)}.")
                return "\n---\n".join(parts) if parts else "Results found, but none passed the rigor threshold. Try technical terms."
                
            return "No papers found. Broaden search or check DOI status."
            
        # ── NEW: Fallback for non-SEARCH actions (REFLECT, WRITE, MEMORY, etc.) ──
        if hasattr(chosen, "skill_name") and chosen.skill_name:
            skill = self.skills.get(chosen.skill_name)
            if skill and hasattr(skill, "execute"):
                try:
                    # Dynamically execute the skill and ensure a string is returned
                    result = skill.execute(chosen.payload)
                    return str(result) if result is not None else f"SYSTEM: Action {chosen.action_type} executed successfully but returned no output."
                except Exception as e:
                    logger.error(f"[ACTION] Skill execution failed: {e}", exc_info=True)
                    return f"SYSTEM: Action failed during '{chosen.skill_name}' execution: {str(e)}"

        # ── Ultimate Fallback to guarantee a string return ──
        return f"SYSTEM: Action '{chosen.action_type}' executed but had no specific handler or output."
    
    def _phase_reflection(self, plan: str, result: str) -> str:
        """LLM synthesizes findings into structured insight."""
        from ai.prompts import reflection_prompt
        hierarchy = (
            f"GOAL: {self.state.active_goal_str()}\n"
            f"CHAPTER: {self.state.current_chapter_title}\n"
            f"SUB_GOAL: {self.state.current_sub_goal}"
        )
        # TRUNCATE result here to prevent JSON parse errors and Ollama 500s
        safe_result = str(result)[:1500] 
        return self.llm.complete(reflection_prompt(plan, safe_result, hierarchy))

    def _phase_memory_update(self, reflection: str, chosen: Any) -> None:
        self.state.set_status(AgentStatus.UPDATING_MEMORY)
        
        # Check if the reflection is valid and verified
        is_verified = '"HALLUCINATION_SHIELD": "PASSED"' in reflection
        
        if is_verified:
            # 1. Store ONLY verified data in Semantic Memory
            self.semantic.store(reflection)
            
            # 2. Extract Anchor for STM Pointer
            match = re.search(r"\[REF_\d+\]", reflection)
            anchor_id = match.group(0) if match else "NEW_DATA"
            
            # 3. Push ONLY the light-weight pointer to STM
            self.state.push_short_term(f"Verified and Stored: {anchor_id}")
            self._emit(f"✅ Verified {anchor_id} stored in long-term memory.")
        else:
            # If it fails, we don't store it, and we give the agent a "Failure" hint
            self.state.push_short_term("Last search result FAILED the Hallucination Shield. Search terms were too broad or invalid.")
            self._emit("⚠️ Discarded result: Failed Hallucination Shield or missing DOI.")

        # 4. ALWAYS Clear Perceptions (This flushes the raw 'stack' out of the context window)
        self.state.perceptions = [] 

        # 5. Record to Episodic Log (The forensic trail)
        self.episodic.log(
            action_type=chosen.action_type,
            payload=str(chosen.payload),
            result=f"Status: {'Stored' if is_verified else 'Rejected'}",
            chapter=self.state.current_chapter_title,
            iteration=self.state.iteration,
            success=is_verified
        )

    def _phase_finalize_chapter(self) -> None:
        """Synthesize collected research into a chapter document."""
        static_names = ["Introduction", "Literature_Critique", "Methodology", "Synthesis", "Conclusion"]
        idx = self.state.current_chapter_index
        
        # 1. Resolve Naming
        safe_title = static_names[idx] if idx < len(static_names) else f"Extended_Analysis_{idx + 1}"
        self._emit(f"Synthesizing {safe_title}...")

        # 2. Retrieve Context (with robust fallbacks)
        anchor = f"CHAPTER_{idx + 1}_DATA"
        context_data = self.semantic.retrieve(anchor, k=20)
        
        if not context_data or len(str(context_data)) < 200:
            context_data = self.semantic.retrieve(self.state.current_chapter_title or "Conclusion", k=15)

        grounding = self.semantic.retrieve("CORE_DEFINITIONS", k=1)
        
        # 3. Generate Content
        write_prompt = (
            f"Act as a Rigorous Scientific Reviewer. Write Chapter: '{safe_title}'.\n"
            f"GOAL: {self.state.active_goal_str()}\n"
            f"CONTEXT: {str(context_data)[:8000]}\n"
            "STRICT RULES: Use IEEE citations, formal tone, and summarize key findings."
        )
        final_body = self.llm.complete(write_prompt)

        # 4. Save with Folder Logic
        file_skill = self.skills.get("file_ops")
        filename = f"Chapter_{idx + 1}_{safe_title}"
        
        # Ensure description exists for slugifying
        goal_desc = self.state.active_goal_str() or "research_project"
        topic_folder = FileOpsSkill._slugify(goal_desc)

        file_skill.execute({
            "action": "save_document", 
            "folder": topic_folder,
            "title": filename, 
            "content": final_body
        })
        
        self._emit(f"💾 Saved: {topic_folder}/{filename}.md")

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _grade_evidence(self, url: str, content: str, is_api: bool = False) -> dict:
        """
        Evaluates evidence rigor and semantic relevance.
        """
        goal = self.state.current_goal
        primary = goal.primary_domain.lower() if (goal and goal.primary_domain) else ""
        intersection = goal.intersection_domain.lower() if (goal and goal.intersection_domain) else ""
        
        score = 0.2
        source_type = "Unverified Web"
        content_lower = content.lower()

        trust_domains = [".gov", ".edu", "arxiv", "doi", "nature", "ieee", "sciencedirect", "springer", "acm"]
        if is_api:
            score = 0.5
            source_type = "Peer-Reviewed API"
        elif any(x in url.lower() for x in trust_domains):
            score += 0.4
            source_type = "Academic/Institutional"

        relevance_bonus = 0.0
        if primary and primary in content_lower:
            relevance_bonus += 0.15
        if intersection and intersection in content_lower:
            relevance_bonus += 0.15
        
        if primary and intersection and (primary not in content_lower and intersection not in content_lower):
            score -= 0.3
        
        score += relevance_bonus

        markers = [
            r"\bmethodology\b", r"\bet al\.", r"\[\d+\]", r"\bp-value\b",
            r"\babstract\b", r"\bpeer-reviewed\b", r"\bresults\b", r"\bdataset\b"
        ]
        found = sum(1 for m in markers if re.search(m, content, re.I))
        score += min(0.2, found * 0.03)

        final_score = round(max(0.0, min(1.0, score)), 2)
        
        # BUFFER PROTECTION: Truncating content to 1200 to prevent OOM
        return {
            "content": content[:1200], 
            "score": final_score,
            "type": source_type,
            "url": url,
            "is_relevant": final_score > 0.55 
        }

    def _clean_title(self, t: str) -> str:
        if not isinstance(t, str):
            return str(t)
        t = t.strip()
        t = re.sub(r'^[Tt]itle\s*[:\-\s]+', '', t)
        return t.strip("[]'\" ")

    def _safe_json_parse(self, raw: str, fallback: list) -> list:
        try:
            match = re.search(r"([\[\{].*[\]\}])", raw, re.DOTALL)
            if match:
                clean = re.sub(r',\s*([\]\}])', r'\1', match.group(1))
                return json.loads(clean)
        except Exception:
            pass
        return fallback

    def _emit(self, msg: str) -> None:
        logger.info(msg)
        if self.ui and hasattr(self.ui, "log"):
            self.ui.log(msg)

    def _compress_memory(self, large_text: str) -> str:
        if not self.llm:
            return large_text[:500]

        compression_prompt = (
            "Compress the following research findings into a single dense paragraph. "
            "Keep all DOIs and key numerical metrics. "
            f"Data to compress:\n{large_text}"
        )
        
        try:
            compressed = self.llm.complete(compression_prompt)
            return compressed.strip()
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return large_text[:500]