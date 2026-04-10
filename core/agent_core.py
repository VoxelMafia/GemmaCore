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

from config.settings import settings
from core.state import AgentState, AgentStatus, ActionRecord, Goal
from core.personality import PersonalityEngine
from core.planner import Planner
from memory.short_term import ShortTermMemory
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from memory.long_term import LongTermMemory
from llm.interface import LLMInterface
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
                
                # 3. Re-inject signal only
                if "No relevant memory found" not in summary_text:
                    self.state.push_short_term(f"STRICT GROUNDING FROM PREVIOUS RESEARCH:\n{summary_text}")
                    # Re-store it so retrieve() works in the new session's perception
                    self.semantic.store(f"PREVIOUS_RESEARCH_SUMMARY: {summary_text}")

                logger.info(f"[SYSTEM] Transitioning to {chapter}. Viable points retained.")
                self.state.current_chapter_index = idx
                self.state.current_chapter_title = chapter
                self.state.iteration = 0
                self.state.current_sub_goal = f"Deconstructing {chapter}"
                self.state.source_map = {}

                self._emit(f"Chapter {idx + 1}/{len(self.state.thesis_outline)}: {chapter}")

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
                self._phase_finalize_chapter()

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
        # Planner instance is used directly here
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

        result = self._phase_action(chosen)
        s.last_action_result = result
        self.tracer.record("ACTION", {
            "type": chosen.action_type,
            "payload": str(chosen.payload)[:120],
            "result_excerpt": result[:200],
        })
        logger.info(f"[ACTION] {chosen.action_type} → {result[:80]}")

        # ── 6. REFLECTION ────────────────────────────────────────────────────
        s.set_status(AgentStatus.REFLECTING)
        reflection = self._phase_reflection(raw_plan, result)
        s.last_reflection = reflection
        self.tracer.record("RESULT", {"reflection_excerpt": reflection[:300]})
        logger.info(f"[RESULT] {reflection[:120]}")

        # ── 7. MEMORY UPDATE ─────────────────────────────────────────────────
        s.set_status(AgentStatus.UPDATING_MEMORY)
        self._phase_memory_update(reflection, chosen)
        self.tracer.record("REFLECTION", {"stored": True})
        logger.info("[REFLECTION] Memory updated.")

        # Personality evolution from outcome
        success = len(result) > 100 and "error" not in result.lower()
        self.personality.update_from_outcome("curiosity", success)
        self.personality.update_from_outcome("persistence", success)
        self.personality.apply_to_state(s)

        # Track failures
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
        from ai.prompts import research_gaps_prompt
        s = self.state
        g = s.current_goal

        self._emit(f"🔬 Initiating research scan: {g.description}")

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
        high_rigor = [
            f"SOURCE ({src['type']} RIGOR {src['score']}): {src['content'][:300]}"
            for src in s.source_map.values() if src.get("score", 0) >= 0.6
        ]
        # Fixed: Using correct k as defined in semantic.py
        mem_context = self.semantic.retrieve(s.current_sub_goal, k=4)
        stm_context = self.stm.recent(n=3)
        context = (
            f"GOAL: {s.active_goal_str()}\n"
            f"CHAPTER: {s.current_chapter_title}\n"
            f"SUB_GOAL: {s.current_sub_goal}\n"
            f"VERIFIED_SOURCES:\n" + "\n".join(high_rigor) +
            f"\nRECENT_MEMORY:\n{mem_context}\n"
            f"SHORT_TERM:\n{chr(10).join(stm_context)}"
        )
        return context[:2000]  # Limit perception size to avoid overload
    
    def _phase_reasoning(self, perception: str) -> str:
        """Call LLM with personality-biased planner prompt."""
        from ai.prompts import planner_prompt
        prefix = self.personality.reasoning_prefix()
        augmented = f"[PERSONALITY BIAS]: {prefix}\n\n{perception}"
        # Fixed: Using correct k
        return self.llm.complete(planner_prompt(augmented, self.semantic.retrieve(
            self.state.current_sub_goal, k=6
        )))

    def _phase_action(self, chosen) -> str:
        """Dispatch to the correct skill."""
        s = self.state

        if chosen.action_type == "NAVIGATE":
            url = chosen.payload
            if url in s.attempted_urls:
                return "SYSTEM: Source already analyzed."
            s.attempted_urls.append(url)
            browser = self.skills.get("browser")
            raw = browser.execute({"action": "navigate", "url": url})
            analysis = self._grade_evidence(url, raw, is_api=False)
            s.source_map[url] = analysis
            return f"SOURCE: {url}\nGRADE {analysis['score']}\nCONTENT: {analysis['content'][:1200]}"

        elif chosen.action_type == "SEARCH":
            academic = self.skills.get("academic")
            papers = academic.execute({"query": chosen.payload})
            if isinstance(papers, list) and papers:
                parts = []
                for p in papers:
                    purl = p.get("url") or f"doi:{p.get('doi', 'unknown')}"
                    analysis = self._grade_evidence(purl, p["abstract"], is_api=True)
                    s.source_map[purl] = analysis
                    parts.append(f"DOI: {purl}\nAbstract: {p['abstract'][:800]}")
                return "\n---\n".join(parts)
            else:
                self._emit("⚠️ Academic API empty. Falling back to browser search.")
                browser = self.skills.get("browser")
                return browser.execute({"action": "search", "query": chosen.payload,
                                        "goal": s.current_sub_goal})

        elif chosen.action_type == "REFLECT":
            return f"[REFLECTION PASS] Sub-goal: {chosen.payload}"

        return "[NO ACTION TAKEN]"

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
        
        # 1. Store FULL reflection in Semantic Memory
        self.semantic.store(reflection)

        # 2. Compression for Short-Term Memory
        if len(reflection) > 1200:
            dense_memory = self._compress_memory(reflection)
        else:
            dense_memory = reflection

        # 3. Push to STM
        self.state.push_short_term(dense_memory)
        
        # 4. Record to Episodic Memory using correctly defined 'log'
        self.episodic.log(
            action_type=chosen.action_type,
            payload=str(chosen.payload),
            result=dense_memory,
            chapter=self.state.current_chapter_title,
            iteration=self.state.iteration,
            success=True
        )

    def _phase_finalize_chapter(self) -> None:
        """Synthesize collected research into a chapter document."""
        static_names = ["Introduction", "Literature_Critique", "Methodology", "Synthesis", "Conclusion"]
        idx = self.state.current_chapter_index
        safe_title = static_names[idx] if idx < len(static_names) else f"Chapter_{idx + 1}"

        self._emit(f"✍️ Synthesizing {safe_title}…")

        anchor = f"CHAPTER_{idx + 1}_DATA"
        # Fixed: k
        context_data = self.semantic.retrieve(anchor, k=20)
        if "No relevant memory" in context_data or len(context_data) < 150:
            context_data = self.semantic.retrieve(self.state.current_chapter_title, k=15)

        grounding = self.semantic.retrieve("CORE_DEFINITIONS", k=1)
        safe_context = str(context_data)[:12000]

        write_prompt = (
            f"Act as a Rigorous Scientific Reviewer. Write Chapter: '{self.state.current_chapter_title}'.\n"
            f"GOAL: {self.state.active_goal_str()}\n"
            f"CORE DEFINITIONS: {grounding}\n"
            f"RESEARCH DATA: {safe_context}\n"
            "STRICT RULES:\n"
            "1. Use a formal, peer-reviewed tone.\n"
            "2. Ground all claims in the RESEARCH DATA provided.\n"
            "3. Cite findings explicitly via DOIs found in research.\n"
            "4. Write at least 800 words."
        )

        final_body = self.llm.complete(write_prompt)

        if len(final_body) < 600:
            self._emit(f"⚠️ {safe_title} too thin. Retrying…")
            expanded = self.semantic.retrieve(self.state.active_goal_str(), k=10)
            final_body = self.llm.complete(write_prompt + f"\nSUPPLEMENTAL DATA: {str(expanded)[:4000]}")

        file_skill = self.skills.get("file_ops")
        filename = f"Chapter_{idx + 1}_{safe_title}"
        file_skill.execute({
            "action": "save_document", 
            "path": f"{filename}.md",  # Add this
            "title": filename, 
            "content": final_body
        })
        self._emit(f"💾 Saved: {filename}")

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