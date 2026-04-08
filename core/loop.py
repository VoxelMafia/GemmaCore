import threading
import time
import re
import random
from ai.llm import ask_llm
from ai.prompts import planner_prompt, reflection_prompt
from utils.url import normalize_url
from config import MAX_ITERATIONS

class AgentLoop:
    def __init__(self, agent):
        self.agent = agent
        self.goal = ""
        self.iteration = 0
        self.attempted_urls = set()
        self.attempted_queries = set()
        self.source_map = {} # { "canonical_url": "Snippet/Title" }
        self.consecutive_failures = 0

    def set_goal(self, goal):
        self.goal = goal
        self.iteration = 0

    def start(self):
        threading.Thread(target=self.run, daemon=True).start()

    def stop(self):
        self.agent.running = False

    def run(self):
        # Local imports inside thread
        from skills.browser import BrowserSkill
        from skills.filesystem import FilesystemSkill

        self.browser = BrowserSkill(self.agent)
        self.files = FilesystemSkill(self.agent)

        # --- STEP 0: DIRECT ENTRY PATCH (Strict Regex) ---
        # Capture URLs while excluding surrounding Markdown characters
        # (backticks, quotes, angle brackets, closing parens/brackets/braces).
        url_pattern = r"(?P<url>https?://[^\s`<>\"'\)\]\}]+)"
        url_match = re.search(url_pattern, self.goal)

        if url_match:
            # Prefer the named capture to avoid grabbing surrounding punctuation
            target_url = url_match.group('url').strip("`'\"().,[]{} ")
            # normalize before storing so dedupe and history use canonical form
            target_url = normalize_url(target_url)
            # Record that we're attempting this URL (optimistic; will be authoritative on success)
            self.attempted_urls.add(target_url)
            self.agent.ui.log(f"🎯 Direct URL detected: {target_url}")

            # REQUEST APPROVAL: For safety, ask the operator before navigating to an external URL.
            try:
                approved = self.agent.approval.request(f"Navigate to direct URL: {target_url}")
            except Exception:
                approved = False

            if not approved:
                self.agent.ui.log("🚫 Direct-URL navigation rejected by operator. Continuing with iterative plan.")
            else:
                self.agent.ui.log(f"🚀 Approved. Navigating to: {target_url}")
                result = self.browser.navigate(target_url)
                # detect error-like results and register successful sources
                error_keywords = ["timeout", "exceeded", "failed to load", "error", "404", "junk", "low quality"]
                is_error = any(kw in str(result).lower() for kw in error_keywords)
                if not is_error:
                    self.source_map[target_url] = str(result)[:100].replace("\n", " ")
                reflection = ask_llm(reflection_prompt("INITIAL_NAV", result, self.goal))
                self.agent.memory.store(reflection)
                self.iteration = 1

        while self.agent.running:
            if self.iteration >= MAX_ITERATIONS:
                self.agent.ui.log("⚠️ Max research iterations reached. Synthesizing final report...")
                self._finalize_report()
                break

            self.agent.ui.log(f"\n🔁 Iteration {self.iteration}")
            
            # 1. Retrieve Context & Plan
            context = self.agent.memory.get_context(self.goal, n_results=15) 
            plan = ask_llm(planner_prompt(self.goal, context))
            self.agent.ui.log(f"🧠 Plan:\n{plan}")

            # 2. Human-in-the-loop Approval
            if not self.agent.approval.request(plan):
                self.agent.ui.log("❌ Action rejected")
                continue

            # 3. EXECUTION ROUTING
            result = ""
            plan_upper = plan.upper()

            if "WRITE_DOC" in plan_upper or "WRITE_FILE" in plan_upper:
                self._save_article(plan)
                break 

            elif "NAVIGATE:" in plan_upper:
                # Use the stricter URL pattern to avoid %60/backtick issues
                nav_match = re.search(url_pattern, plan)
                if nav_match:
                    target_url = nav_match.group('url').strip("`'\"().,[]{} ")
                    target_url = normalize_url(target_url)
                    # Skip if we've already tried this URL
                    if target_url in self.attempted_urls:
                        system_msg = f"SYSTEM: You already tried {target_url} and it failed or was completed. You MUST choose a completely different URL or search term."
                        self.agent.memory.store(system_msg)
                        self.agent.ui.log(f"⚠️ Skipping previously attempted URL: {target_url}")
                        self.iteration += 1
                        time.sleep(random.uniform(1.0, 3.0))
                        continue

                    self.agent.ui.log(f"🚀 Moving to sub-resource: {target_url}")
                    # Record executed URL
                    self.attempted_urls.add(target_url)
                    result = self.browser.navigate(target_url)
                    # detect error-like results and register successful sources
                    error_keywords = ["timeout", "exceeded", "failed to load", "error", "404", "junk", "low quality"]
                    is_error = any(kw in str(result).lower() for kw in error_keywords)
                    if not is_error:
                        self.source_map[target_url] = str(result)[:100].replace("\n", " ")
                else:
                    result = "Error: NAVIGATE requested but no URL found in plan."

            else:
                # Fallback to search
                query = self._smart_parse(plan)
                # Note: do NOT skip queries even if they've been attempted before.
                # We only deduplicate URL navigations to avoid clicking the same link twice.
                # Decide whether to prefer authoritative sources based on plan hints
                lower_plan = plan.lower()
                force_authoritative = any(k in lower_plan for k in ["institutional", "authoritative", "site:.gov", "site:.edu", "site:.org", "gov", "academic", "peer-reviewed"]) or ("query a (institutional)" in lower_plan)

                # For the first iteration prefer the exact LLM-provided query (useful for names/topics).
                # On subsequent iterations build a canonical transformed query for dedupe/logging.
                # Use the LLM-extracted query directly for both initial and subsequent searches.
                # We intentionally avoid internal transformation here so the agent's
                # original search intent (especially names/operators) remains intact.
                canonical_q = query.strip()
                if self.iteration == 0:
                    self.agent.ui.log(f"🔁 Using raw initial query: {canonical_q}")
                canonical_q_norm = re.sub(r"\s+", " ", canonical_q.strip().lower())

                # Do not auto-skip canonical queries even if seen before; allow retries with
                # different browsing behavior or search gateway. We still record the
                # canonical query after executing the search below.

                error_keywords = ["timeout", "exceeded", "failed to load", "error", "404", "junk", "low quality"]
                self.agent.ui.log(f"🔁 Canonical query: {canonical_q}")

                # Execute the canonical query using the BrowserSkill (uses DuckDuckGo HTML gateway)
                try:
                    # Pass raw=True on the first iteration so the BrowserSkill uses the exact query
                    use_raw = (self.iteration == 0)
                    result = self.browser.search(canonical_q, goal=self.goal, raw=use_raw)
                except Exception as e:
                    self.agent.ui.log(f"⚠️ Search execution failed: {e}")
                    result = f"ERROR: Search exception: {str(e)}"

                is_error = any(kw in str(result).lower() for kw in error_keywords)
                self.attempted_queries.add(canonical_q_norm)
                if is_error:
                    self.agent.ui.log("⚠️ Research failure. Storing warning.")
                    # Force a warning into memory so the LLM changes strategy next iteration
                    reflection = f"STRICT_WARNING: The action for '{self.goal}' failed. Try a different URL or search query."
                    self.agent.memory.store(reflection)
                else:
                    reflection = ask_llm(reflection_prompt(plan, result, self.goal))
                    if "ERROR" in reflection.upper():
                        self.agent.ui.log("⚠️ Content flagged as low quality.")
                        self.agent.memory.store(f"SKIP: Last result was poor quality.")
                        self.consecutive_failures += 1
                    else:
                        self.agent.memory.store(reflection)

            self.agent.ui.log(f"📈 {reflection[:120]}...")
            self.iteration += 1
            time.sleep(random.uniform(1.0, 3.0))

    def _finalize_report(self):
        all_research = self.agent.memory.get_context(self.goal, n_results=25)
        # Strongly instruct the LLM to return only human-readable Markdown.
        summary_prompt = (
            "You are a professional research writer. Produce a final report in Markdown only. "
            "DO NOT output JSON, YAML front-matter as code blocks, ACTION blocks, or any machine-readable metadata. "
            "Do not include fenced code blocks of any kind. Start the output with the literal token 'CONTENT:' followed by the article markdown (title, headings, sections, references). "
            f"GOAL: {self.goal}\nRESEARCH: {all_research}\n\nReturn only Markdown text that begins with 'CONTENT:' and nothing else."
        )

        final_content = ask_llm(summary_prompt)

        # Sanitize: remove any leftover fenced code blocks (e.g., ```json ... ```)
        try:
            final_content = re.sub(r"```[\s\S]*?```", "", final_content)
            # Collapse repeated blank lines
            final_content = re.sub(r"\n{3,}", "\n\n", final_content).strip()
        except Exception:
            pass

        # Inject a static verified-sources section from recorded navigations
        try:
            final_content = self._inject_static_sources(final_content)
        except Exception:
            pass

        # Run final verification, metadata-to-body sync, and acronym checks
        try:
            final_content = self._verify_and_sync_report(final_content)
        except Exception as e:
            # If verification fails for any reason, log and continue with best-effort content
            self.agent.ui.log(f"⚠️ Final verification failed: {e}")

        self._save_article(final_content)

    def _save_article(self, content_str):
        try:
            # Prefer explicit ACTION JSON blocks with WRITE_DOC command
            content_part = None
            doc_title = None

            # Look for ```json blocks and try to parse ACTION block first
            json_blocks = re.findall(r"```json\s*(\{[\s\S]*?\})\s*```", content_str, flags=re.IGNORECASE)
            for jb in json_blocks:
                try:
                    import json as _json
                    parsed = _json.loads(jb)
                    # If this block contains a WRITE_DOC action, prefer it
                    if isinstance(parsed, dict) and parsed.get("command") == "WRITE_DOC":
                        doc_title = parsed.get("title")
                        content_part = parsed.get("content")
                        break
                except Exception:
                    continue

            # If not found in ACTION JSON, try an ACTION: ```json { ... } ``` pattern
            if content_part is None:
                action_match = re.search(r"ACTION:\s*```json\s*(\{[\s\S]*?\})\s*```", content_str, flags=re.IGNORECASE)
                if action_match:
                    try:
                        import json as _json
                        parsed = _json.loads(action_match.group(1))
                        if parsed.get("command") == "WRITE_DOC":
                            doc_title = parsed.get("title")
                            content_part = parsed.get("content")
                    except Exception:
                        pass

            # Fall back to 'CONTENT:' marker or use the whole string
            if content_part is None:
                if "CONTENT:" in content_str.upper():
                    content_part = content_str.split("CONTENT:", 1)[1].strip()
                else:
                    content_part = content_str

            # If the JSON ACTION provided a title, use it; otherwise fall back to goal
            use_title = doc_title if doc_title else self.goal
            status = self.files.save_document(title=use_title, content=content_part)
            self.agent.ui.log(f"✅ {status}")
        except Exception as e:
            self.agent.ui.log(f"❌ Failed to write: {e}")

    def _inject_static_sources(self, content_part):
        """Append a verified 'Research Sources' section from recorded successful navigations."""
        if not getattr(self, 'source_map', None):
            return content_part

        sources_md = "\n\n--- \n### ## Research Sources (Verified)\n"
        for url, snippet in self.source_map.items():
            # Use the URL as the display name for static reliability
            safe_snip = (snippet or '').strip()
            sources_md += f"* [{url}]({url}) - *{safe_snip}...*\n"

        return content_part + sources_md

    def _smart_parse(self, plan):
        """Extracts the query from 'SEARCH: "query"' or falls back to first line."""
        try:
            # Loosen matching to catch many LLM output formats such as:
            # SEARCH: Bitcoin
            # SEARCH: "Bitcoin"
            # SEARCH: ['Bitcoin']
            # Also tolerate stray colons/spaces after the token.
            match = re.search(r"SEARCH:\s*[:\s]*['\"\[]?(.*?)['\"\]]?(\n|$)", plan, re.IGNORECASE)
            if match:
                query = match.group(1).strip()
                return query.strip('[]"\'')

            # Fallback split logic (case-insensitive)
            plan_upper = plan.upper()
            if "SEARCH:" in plan_upper:
                query_part = plan.split(re.compile('SEARCH:', re.IGNORECASE).search(plan).group(0))[1]
                return query_part.split("\n")[0].strip().strip('[]"\'')
        except:
            pass

        # Final Fallback: choose a first non-meta line (avoid using plan headers)
        lines = [l.strip() for l in plan.split('\n') if l.strip()]
        for line in lines:
            # skip meta-like or conversational plan lines
            if re.search(r"\b(plan|brief plan|emit|using raw|canonical|searching:|searching|okay,|okay|my brief|my plan|plan:)\b", line, re.IGNORECASE):
                continue
            # skip very short non-descriptive lines
            if len(line) < 15 and not re.search(r"\w+\s+\w+", line):
                continue
            return line[:200]

        # Fallback to the agent goal if available, otherwise a generic label
        try:
            return self.goal if hasattr(self, 'goal') and self.goal else "general research"
        except:
            return "general research"

        def _verify_and_sync_report(self, content_str):
            """Ensure metadata (YAML frontmatter) matches body, validate key acronyms, and align dates.

            This function is conservative: it only auto-fixes known Arctic acronyms (e.g., TSP -> Thermal State of Permafrost).
            For metadata mismatches it will ask the LLM to rewrite a minimal YAML frontmatter block that matches the body.
            """
            # Extract main article content (reuse logic similar to _save_article)
            content_part = None
            if "CONTENT:" in content_str.upper():
                content_part = content_str.split("CONTENT:", 1)[1].strip()
            else:
                content_part = content_str

            # Detect YAML frontmatter
            yaml_front = None
            yaml_match = re.search(r"^---\s*\n([\s\S]*?)\n---\s*\n", content_part)
            if yaml_match:
                yaml_front = yaml_match.group(1)

            # Extract introduction: first non-empty paragraph after frontmatter and title
            body_after = content_part
            if yaml_match:
                body_after = content_part[yaml_match.end():]

            # Remove leading title if present (e.g., # Title) to get to introduction
            body_after = re.sub(r"^#.*\n", "", body_after).lstrip()
            paragraphs = [p.strip() for p in re.split(r"\n\n+", body_after) if p.strip()]
            intro = paragraphs[0] if paragraphs else ""

            # Parse summary from YAML if present
            summary = None
            title = None
            date_in_yaml = None
            if yaml_front:
                for line in yaml_front.splitlines():
                    if ':' not in line:
                        continue
                    k, v = line.split(':', 1)
                    key = k.strip().lower()
                    val = v.strip().strip('"\'')
                    if key == 'summary':
                        summary = val
                    if key == 'title':
                        title = val
                    if key == 'date':
                        date_in_yaml = val

            # Check alignment: summary should overlap with introduction
            def overlap_ratio(a, b):
                aw = set(re.findall(r"\w+", (a or '').lower()))
                bw = set(re.findall(r"\w+", (b or '').lower()))
                if not aw or not bw:
                    return 0.0
                return len(aw & bw) / float(len(aw))

            need_metadata_update = False
            if summary:
                ratio = overlap_ratio(summary, intro)
                if ratio < 0.4:
                    need_metadata_update = True
            else:
                need_metadata_update = True

            # If mismatch detected, ask LLM to produce a concise YAML frontmatter matching the body
            if need_metadata_update:
                prompt = (
                    "You are a strict metadata editor. Given the following article body, produce only a YAML frontmatter block (--- to ---)"
                    " containing `title`, `summary` (one sentence), and `date` in YYYY-MM-DD format that accurately reflect the primary subject in the Introduction."
                    " Do NOT invent institutions or extra fields. Return only the YAML block.\n\n"
                    f"ARTICLE_BODY:\n{body_after[:8000]}"
                )
                try:
                    meta_resp = ask_llm(prompt)
                    # Extract YAML block from response
                    meta_match = re.search(r"---\s*\n([\s\S]*?)\n---", meta_resp)
                    if meta_match:
                        new_yaml = meta_match.group(0)
                        # Replace existing frontmatter or prepend
                        if yaml_match:
                            content_part = content_part[:yaml_match.start()] + new_yaml + "\n" + content_part[yaml_match.end():]
                        else:
                            content_part = new_yaml + "\n" + content_part
                        content_str = content_part
                except Exception:
                    # If LLM fails, leave content unchanged but store a memory note
                    self.agent.memory.store("WARN: Metadata sync step failed during finalization.")

            # Date consistency: ensure header date and any date found in body match
            # If YAML date present, search body for date string (YYYY-) and if different, replace YAML date with body date or today's date
            if yaml_match:
                yaml_block = yaml_match.group(0)
                if date_in_yaml:
                    body_date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", body_after)
                    if body_date_match and body_date_match.group(1) != date_in_yaml:
                        new_date = body_date_match.group(1)
                        new_yaml_block = re.sub(r"date:\s*.*", f"date: {new_date}", yaml_block)
                        content_part = content_part.replace(yaml_block, new_yaml_block)
                        content_str = content_part

            # Acronym validation: conservative auto-fix for known Arctic acronym TSP
            # If 'TSP' appears and not expanded, expand to 'TSP (Thermal State of Permafrost)' on first occurrence.
            if re.search(r"\bTSP\b", content_str) and "Thermal State of Permafrost" not in content_str:
                content_str = re.sub(r"\bTSP\b", "TSP (Thermal State of Permafrost)", content_str, count=1)

            # Scan for other 2-5 letter all-caps acronyms and log unknown ones for operator review
            acronyms = set(re.findall(r"\b([A-Z]{2,5})\b", content_str))
            known = {"TSP"}
            unknown = [a for a in acronyms if a not in known]
            if unknown:
                note = f"ACRONYM_CHECK: Found acronyms needing verification: {', '.join(unknown)}"
                self.agent.ui.log("⚠️ " + note)
                self.agent.memory.store(note)

            # Final content returned
            return content_str