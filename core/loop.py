import threading
import time
import re
import random
from ai.llm import ask_llm
from ai.prompts import planner_prompt, reflection_prompt
from config import MAX_ITERATIONS

class AgentLoop:
    def __init__(self, agent):
        self.agent = agent
        self.goal = ""
        self.iteration = 0

    def set_goal(self, goal):
        self.goal = goal
        self.iteration = 0

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def stop(self):
        self.agent.running = False

    def run(self):
        # Local imports inside thread to avoid issues
        from skills.browser import BrowserSkill
        from skills.filesystem import FilesystemSkill 
        
        self.browser = BrowserSkill(self.agent)
        self.files = FilesystemSkill(self.agent)

        while self.agent.running:
            # --- FINAL SUMMARY LOGIC ---
            # Synthesize all compressed memories into a final "uncompressed" report
            if self.iteration >= MAX_ITERATIONS:
                self.agent.ui.log("⚠️ Max research iterations reached. Synthesizing final report...")
                self._finalize_report()
                break

            self.agent.ui.log(f"\n🔁 Iteration {self.iteration}")
            
            # 1. Retrieve compressed memory context
            # We can pull more results (n=15) because the reflections are now compressed/tiny
            context = self.agent.memory.get_context(self.goal, n_results=15) 
            plan = ask_llm(planner_prompt(self.goal, context))
            self.agent.ui.log(f"🧠 Plan:\n{plan}")

            # 2. Human-in-the-loop Approval
            if not self.agent.approval.request(plan):
                self.agent.ui.log("❌ Action rejected")
                continue

            # 3. Check for Writing intent
            # Note: The prompt now tells the LLM to "re-hydrate" compressed data here
            if "WRITE_DOC" in plan.upper() or "WRITE_FILE" in plan.upper():
                self._save_article(plan)
                break 

            # 4. Search and Self-Correction Logic
            else:
                query = self._smart_parse(plan)
                self.agent.ui.log(f"🔍 Searching for: {query}")
                
                # Execute search
                result = self.browser.search(query)

                # --- ERROR VALIDATION & FAILURE MEMORY ---
                error_keywords = ["timeout", "exceeded", "failed to load", "error", "404", "junk", "low quality"]
                is_error = any(kw in str(result).lower() for kw in error_keywords)

                if is_error:
                    self.agent.ui.log("⚠️ Research failure. Storing warning in memory to avoid loops.")
                    # We store the failure so the LLM knows NOT to repeat this query in the next iteration
                    reflection = f"STRICT_WARNING: The search for '{query}' failed or returned junk. Try a completely different approach/keywords."
                    self.agent.memory.store(reflection)
                else:
                    # Normal reflection process (which now uses Compression Logic)
                    reflection = ask_llm(reflection_prompt(plan, result))
                    
                    if "ERROR" in reflection.upper():
                        self.agent.ui.log("⚠️ Content flagged as low quality by Reflection logic.")
                        self.agent.memory.store(f"SKIP: Source for '{query}' was poor quality.")
                    else:
                        self.agent.memory.store(reflection)
                # -------------------------

                self.agent.ui.log(f"📈 {reflection[:120]}...")

            self.iteration += 1
            time.sleep(random.uniform(1.0, 3.0))

    def _finalize_report(self):
        """Forces a final uncompressed synthesis using all available research seeds."""
        # Grab a massive chunk of compressed memory (up to 25 snippets)
        all_research = self.agent.memory.get_context(self.goal, n_results=25)
        
        summary_prompt = f"""
        GOAL: {self.goal}
        COMPRESSED RESEARCH SEEDS:
        {all_research}
        
        The research phase is over. Your task is to UNCOMPRESS and RE-HYDRATE the data above.
        Write a comprehensive, professional, and long-form markdown article.
        Ensure all technical facts and numbers are preserved and expanded into flowing prose.
        
        Start your response with 'CONTENT:' followed by the markdown text.
        """
        
        final_content = ask_llm(summary_prompt)
        self._save_article(final_content)

    def _save_article(self, content_str):
        """Helper to parse content and save using dynamic slugified naming."""
        try:
            # Handle potential title extraction if provided in the plan
            # Format: WRITE_DOC: "Title" | CONTENT: ...
            content_part = content_str
            if "CONTENT:" in content_str.upper():
                content_part = content_str.split("CONTENT:")[1].strip()
            
            # Use save_document to handle slugification (e.g., "Research Goal" -> "research-goal.md")
            status = self.files.save_document(title=self.goal, content=content_part)
            self.agent.ui.log(f"✅ {status}")
        except Exception as e:
            self.agent.ui.log(f"❌ Failed to write: {e}")

    def _smart_parse(self, plan):
        """Extracts search query from plan with safety fallback."""
        match = re.search(r"['\"](.*?)['\"]", plan)
        if match and len(match.group(1)) > 3:
            return match.group(1)[:80]
        return plan.split('\n')[0][:80]