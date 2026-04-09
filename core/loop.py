import threading
import time
import re
import random
import json
from ai.llm import ask_llm
from ai.prompts import planner_prompt, reflection_prompt, research_gaps_prompt
from utils.url import normalize_url
from config import MAX_ITERATIONS
from utils import logger as ulogger

class AgentLoop:
    def __init__(self, agent):
        self.agent = agent
        self.overall_thesis_goal = ""
        self.thesis_outline = []
        self.current_chapter_index = 0
        self.current_chapter_title = ""
        self.current_sub_goal = ""
        self.iteration = 0
        self.attempted_urls = set()
        self.source_map = {} 
        self.consecutive_failures = 0 # Track for loop health

    def set_goal(self, goal):
        self.iteration = 0
        self.thesis_outline = []
        if isinstance(goal, dict):
            self.agent.metadata = goal
            pd = goal.get('primary_domain', '') or ''
            idom = goal.get('intersection_domain', '') or ''
            self.overall_thesis_goal = f"{pd} AND {idom}" if pd and idom else (pd or idom or "")
        elif isinstance(goal, (list, tuple)) and len(goal) >= 2:
            self.agent.metadata = {'primary_domain': goal[0], 'intersection_domain': goal[1]}
            self.overall_thesis_goal = f"{goal[0]} AND {goal[1]}"
        else:
            self.overall_thesis_goal = goal

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def stop(self):
        self.agent.running = False

    def run(self):
        from skills.browser import BrowserSkill
        from skills.academic import AcademicSkill
        from skills.filesystem import FilesystemSkill
        
        self.browser = BrowserSkill(self.agent)
        self.academic = AcademicSkill(self.agent)
        self.files = FilesystemSkill(self.agent)

        # --- PHASE 1: RESEARCH GAP IDENTIFICATION ---
        # RESTORED: Full Domain Parsing Logic from original helpers
        metadata = getattr(self.agent, 'metadata', None) or {}
        primary = 'Emerging Tech'
        intersection = 'Sustainability'

        if metadata:
            primary = metadata.get('primary_domain', primary)
            intersection = metadata.get('intersection_domain', intersection)
        else:
            try:
                from utils.helpers import parse_goal_string
                parsed = parse_goal_string(self.overall_thesis_goal or "")
                if parsed:
                    primary = parsed.get('primary_domain', primary)
                    intersection = parsed.get('intersection_domain', intersection)
                else:
                    if isinstance(self.overall_thesis_goal, str) and self.overall_thesis_goal.strip():
                        primary = self.overall_thesis_goal.strip()
                        intersection = ''
                ulogger.log(f"Parsed domains: {primary} / {intersection}", level="DEBUG")
            except Exception as e:
                ulogger.log(f"Domain parsing failed: {e}", level="WARN")

        label = f"{primary} ∩ {intersection}" if intersection else primary
        self.agent.ui.log(f"Initiating Verified Research Scan: {label}")
        
        # Determine Research Thesis Goal
        if self.overall_thesis_goal and str(self.overall_thesis_goal).strip().lower() != "autonomous":
            self.agent.ui.log(f"Using provided thesis goal: {self.overall_thesis_goal}")
        else:
            topic_prompt = research_gaps_prompt(primary, intersection)
            raw_suggestions = ask_llm(topic_prompt)
            suggestions = self._safe_json_parse(raw_suggestions, ["Adaptive Systems: Gap in real-time verification"])
            self.overall_thesis_goal = self._clean_title(suggestions[0])
            self.agent.ui.log(f"Selected research gap: {self.overall_thesis_goal}")

        # --- PHASE 2: STRATEGIC OUTLINING ---
        # # 1. Generate Formal Structure
        outline_prompt = (
            f"Create a formal 5-chapter thesis outline for: {self.overall_thesis_goal}. "
            "Structure: Introduction, Literature Critique, Methodology, Empirical Synthesis, Conclusion. "
            "Return ONLY a JSON list of strings."
        )
        raw_outline = self._safe_json_parse(ask_llm(outline_prompt), 
            ["Introduction", "Literature Critique", "Methodology", "Synthesis", "Conclusion"])
        
        self.thesis_outline = [self._clean_title(t) for t in raw_outline]

        # --- PHASE 3: GRADED ITERATIVE RESEARCH ---
        for index, title in enumerate(self.thesis_outline):
            if not self.agent.running: break
            
            self.current_chapter_index = index
            self.current_chapter_title = title
            self.iteration = 0
            self.current_sub_goal = f"Deconstructing {title}"
            self.source_map = {} 

            self.agent.ui.log(f"PROCESSSING CHAPTER {index+1}: {title}")

            while self.iteration < MAX_ITERATIONS and self.agent.running:
                hierarchy = f"GOAL: {self.overall_thesis_goal}\nCHAPTER: {title}\nSUB_GOAL: {self.current_sub_goal}"
                context = self._get_weighted_context()
                
                # Plan Generation
                plan = ask_llm(planner_prompt(hierarchy, context))
                potential_sub_goal = self._extract_sub_goal(plan)
                if potential_sub_goal: self.current_sub_goal = potential_sub_goal

                # UI Approval Request
                self.agent.ui.log(f"⏳ Waiting for approval on: {self.current_sub_goal[:60]}...")
                if not self.agent.approval.request(plan):
                    ulogger.log("User rejected plan iteration.", level="INFO")
                    continue

                result_data = ""
                # ACTION BRANCH: Browser Navigation
                if "NAVIGATE:" in plan.upper():
                    url_match = re.search(r"https?://[^\s`<>\"'\)\]\}]+", plan)
                    if url_match:
                        target_url = normalize_url(url_match.group(0).strip("`'\"().,[]{} "))
                        if target_url in self.attempted_urls:
                            result_data = "SYSTEM: Source already analyzed."
                        else:
                            self.attempted_urls.add(target_url)
                            raw_content = self.browser.navigate(target_url)
                            analysis = self._grade_evidence(target_url, raw_content)
                            self.source_map[target_url] = analysis
                            result_data = f"SOURCE: {target_url}\nGRADE {analysis['score']}\nCONTENT: {analysis['content'][:1500]}"
                
                # ACTION BRANCH: Academic API Search
                else:
                    # RESTORED: Full Query Normalization Logic
                    raw_query = self._smart_parse(plan).replace('"', '').replace("'", "")
                    api_query = re.sub(r"[\(\)]", "", raw_query)
                    api_query = re.sub(r"\b(AND|OR)\b", "", api_query, flags=re.I)
                    api_query = ' '.join(api_query.split())

                    # RESTORED: Verbose ulogger Telemetry
                    ulogger.log(f"Initiating Academic API query: {api_query}", level="DEBUG", component="Academic")
                    api_data = self.academic.search(api_query)

                    if isinstance(api_data, list) and len(api_data) > 0:
                        formatted_papers = []
                        for paper in api_data:
                            paper_url = paper.get('url') or f"doi:{paper.get('doi')}"
                            analysis = self._grade_evidence(paper_url, paper['abstract'], is_api_result=True)
                            self.source_map[paper_url] = analysis
                            formatted_papers.append(f"DOI: {paper_url}\nAbstract: {paper['abstract'][:1000]}")
                        result_data = "\n---\n".join(formatted_papers)
                        self.consecutive_failures = 0
                    else:
                        ulogger.log(f"Academic API returned no results for '{api_query}'", level="INFO", component="Academic")
                        self.agent.ui.log("⚠️ API yields no results. Falling back to Browser.")
                        result_data = self.browser.search(raw_query, goal=self.current_sub_goal)
                        self.consecutive_failures += 1

                # UPGRADE: DUAL-INDEX REFLECTION
                self.agent.ui.log(f"🧠 Synthesizing findings for {title} (Step {self.iteration+1})...")
                reflection = ask_llm(reflection_prompt(plan, str(result_data), hierarchy))
                
                # Anchor key ensures the synthesizer always finds this chapter's data
                static_key = f"CHAPTER_{index+1}_DATA"
                self.agent.memory.store(f"{static_key}: {reflection}")
                self.agent.memory.store(f"{title}: {reflection}") # Fuzzy search index
                            
                self.iteration += 1
                time.sleep(random.uniform(0.5, 1.5))

            # Trigger Chapter Synthesis
            self._finalize_chapter()

        self.agent.ui.log("✅ Full Thesis Synthesis Complete.")
        if hasattr(self, 'browser'): self.browser.stop()

    def _finalize_chapter(self):
        # RESTORED: Explicit Phase Headers
        static_names = ["Introduction", "Literature_Critique", "Methodology", "Synthesis", "Conclusion"]
        
        # 1. Filename Mapping
        if self.current_chapter_index < len(static_names):
            safe_title = static_names[self.current_chapter_index]
        else:
            safe_title = f"Chapter_{self.current_chapter_index + 1}"

        self.agent.ui.log(f"Synthesizing {safe_title}...")

        # 2. UPGRADE: Robust Context Retrieval
        mem_key = f"CHAPTER_{self.current_chapter_index + 1}_DATA"
        context_data = self.agent.memory.get_context(mem_key, n_results=20)
        
        # RESTORED: Redundant Memory Validation (Phase 3 Check)
        if not context_data or len(str(context_data)) < 150:
            ulogger.log(f"Static anchor {mem_key} empty. Falling back to fuzzy search.", level="WARN")
            context_data = self.agent.memory.get_context(self.current_chapter_title, n_results=15)

        grounding = self.agent.memory.get_context("CORE_DEFINITIONS", n_results=1)
        
        # 3. UPGRADE: Context Truncation (Safety Valve)
        safe_context = str(context_data)[:12000]

        write_prompt = (
            f"Act as a Rigorous Scientific Reviewer. Write Chapter: '{self.current_chapter_title}'.\n"
            f"GOAL: {self.overall_thesis_goal}\n"
            f"CORE DEFINITIONS: {grounding}\n"
            f"RESEARCH DATA: {safe_context}\n"
            "STRICT RULES:\n"
            "1. Use a formal, peer-reviewed tone.\n"
            "2. Ground all claims in the RESEARCH DATA provided.\n"
            "3. Cite findings explicitly (e.g., 'Recent data suggests...').\n"
            "4. Write at least 800 words."
        )

        self.agent.ui.log(f"LLM drafting {safe_title} content...")
        final_body = ask_llm(write_prompt)

        # 4. UPGRADE: SUCCESSION LOGIC (Self-Correction)
        if len(final_body) < 600:
            self.agent.ui.log(f"⚠️ {safe_title} too thin. Retrying with expanded memory search...")
            expanded_context = self.agent.memory.get_context(self.overall_thesis_goal, n_results=10)
            final_body = ask_llm(write_prompt + f"\nSUPPLEMENTAL DATA: {str(expanded_context)[:4000]}")

        # 5. Save document
        filename = f"Chapter_{self.current_chapter_index + 1}_{safe_title}"
        self.files.save_document(title=filename, content=final_body)
        self.agent.ui.log(f"Successfully saved: {filename}")

    def _grade_evidence(self, url, content, is_api_result=False):
        # RESTORED: Expanded Score Markers and Logic
        if is_api_result:
            return {"content": content, "score": 0.95, "type": "Peer-Reviewed", "url": url}
            
        score = 0.3
        source_type = "Web Insight"
        
        # Academic/Institutional Bonus
        academic_domains = [".gov", ".edu", "arxiv", "doi", "nature", "ieee", "researchgate", "science.org"]
        if any(x in url.lower() for x in academic_domains):
            score += 0.5
            source_type = "Academic/Peer-Reviewed"
        
        # Rigor markers
        markers = [
            r"\bmethodology\b", r"\bet al\.", r"\[\d+\]", r"\bp-value\b", 
            r"\babstract\b", r"\bresults\b", r"\bdiscussion\b", r"\bconclusion\b"
        ]
        found = sum(1 for m in markers if re.search(m, content, re.I))
        score += min(0.2, found * 0.025)

        return {
            "content": content[:2500],
            "score": round(min(score, 1.0), 2),
            "type": source_type,
            "url": url
        }

    def _get_weighted_context(self):
        # Truncated research history to keep prompt clean
        high_rigor = [
            f"SOURCE ({s['type']} - RIGOR {s['score']}): {s['content'][:700]}"
            for s in self.source_map.values() if s['score'] >= 0.6
        ]
        history = str(self.agent.memory.get_context(self.current_sub_goal, n_results=6))[:4500]
        return "VERIFIED EVIDENCE:\n" + "\n\n".join(high_rigor) + f"\n\nPRIOR FINDINGS:\n{history}"

    def _clean_title(self, t):
        if not isinstance(t, str): return t
        t = t.strip()
        t = re.sub(r'^[Tt]itle\s*[:\-\s]+', '', t)
        t = t.strip("[]'\" ")
        return t

    def _extract_sub_goal(self, plan):
        match = re.search(r"SUB_GOAL:\s*(.*)", plan, re.I)
        return match.group(1).strip() if match else None

    def _safe_json_parse(self, raw, fallback):
        # RESTORED: Full robust parsing logic from loop.py
        try:
            match = re.search(r"([\[\{].*[\]\}])", raw, re.DOTALL)
            if match:
                clean_json = match.group(1)
                clean_json = re.sub(r',\s*([\]\}])', r'\1', clean_json)
                return json.loads(clean_json)
            return fallback
        except (json.JSONDecodeError, AttributeError, Exception) as e:
            ulogger.log(f"JSON Parse Error: {str(e)[:50]}", level="ERROR")
            return fallback

    def _smart_parse(self, plan):
        # RESTORED: Full SEARCH parsing regex
        match = re.search(r"SEARCH:\s*[:\s]*['\"\[]?(.*?)['\"\]]?(\n|$)", plan, re.I)
        return match.group(1).strip("[]' ") if match else self.overall_thesis_goal