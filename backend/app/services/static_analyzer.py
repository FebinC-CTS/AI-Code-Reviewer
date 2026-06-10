import subprocess
import json
import logging
import os
import tempfile
from typing import List
from pathlib import Path

from app.models.schemas import ReviewIssue, SeverityLevel

logger = logging.getLogger(__name__)

ESLINT_SEVERITY_MAP = {1: SeverityLevel.MEDIUM, 2: SeverityLevel.HIGH}
BANDIT_SEVERITY_MAP = {
    "LOW": SeverityLevel.LOW,
    "MEDIUM": SeverityLevel.MEDIUM,
    "HIGH": SeverityLevel.HIGH,
}


class StaticAnalyzer:

    def run_eslint(self, file_paths: List[str], base_dir: str) -> List[ReviewIssue]:
        """Run ESLint on JS/TS files. Returns issues or empty list if ESLint not available."""
        js_ts_files = [
            p for p in file_paths
            if Path(p).suffix.lower() in {".js", ".ts", ".jsx", ".tsx"}
        ]
        if not js_ts_files:
            return []

        abs_paths = [os.path.join(base_dir, p) for p in js_ts_files]

        # Write a minimal eslint config if none exists
        eslint_config = os.path.join(base_dir, ".eslintrc.json")
        created_config = False
        if not os.path.exists(eslint_config):
            config = {
                "env": {"browser": True, "es2021": True, "node": True},
                "extends": ["eslint:recommended"],
                "parserOptions": {"ecmaVersion": 2021, "sourceType": "module"}
            }
            with open(eslint_config, "w") as f:
                json.dump(config, f)
            created_config = True

        issues = []
        try:
            result = subprocess.run(
                ["npx", "eslint", "--format", "json", "--no-eslintrc", "-c", eslint_config] + abs_paths,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=base_dir,
            )
            output = result.stdout.strip()
            if not output:
                return []

            eslint_results = json.loads(output)
            for file_result in eslint_results:
                rel_path = os.path.relpath(file_result["filePath"], base_dir).replace("\\", "/")
                for msg in file_result.get("messages", []):
                    sev_int = msg.get("severity", 1)
                    severity = ESLINT_SEVERITY_MAP.get(sev_int, SeverityLevel.MEDIUM)
                    rule = msg.get("ruleId") or "unknown-rule"
                    message = msg.get("message", "")
                    line = msg.get("line", "?")

                    issues.append(ReviewIssue(
                        file=rel_path,
                        issue=f"ESLint [{rule}]: {message}",
                        severity=severity,
                        explanation=f"ESLint rule '{rule}' violation at line {line}: {message}",
                        fix=msg.get("fix", {}).get("text", "See ESLint documentation for this rule.") or "See ESLint documentation.",
                        recommendation=f"Fix '{rule}' violations. See: https://eslint.org/docs/rules/{rule}",
                        insights="Static analysis finding from ESLint.",
                        source="static",
                    ))
        except FileNotFoundError:
            logger.info("ESLint/npx not found, skipping JS/TS static analysis.")
        except subprocess.TimeoutExpired:
            logger.warning("ESLint timed out.")
        except json.JSONDecodeError as e:
            logger.warning("Could not parse ESLint output: %s", e)
        except Exception as e:
            logger.error("ESLint error: %s", e)
        finally:
            if created_config and os.path.exists(eslint_config):
                os.remove(eslint_config)

        return issues

    def run_stylelint(self, file_paths: List[str], base_dir: str) -> List[ReviewIssue]:
        """Run Stylelint on CSS/SCSS files."""
        css_files = [
            p for p in file_paths
            if Path(p).suffix.lower() in {".css", ".scss", ".sass"}
        ]
        if not css_files:
            return []

        abs_paths = [os.path.join(base_dir, p) for p in css_files]

        # Write minimal stylelint config
        stylelint_config = os.path.join(base_dir, ".stylelintrc.json")
        created_config = False
        if not os.path.exists(stylelint_config):
            config = {"extends": ["stylelint-config-standard"]}
            with open(stylelint_config, "w") as f:
                json.dump(config, f)
            created_config = True

        issues = []
        try:
            result = subprocess.run(
                ["npx", "stylelint", "--formatter", "json"] + abs_paths,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=base_dir,
            )
            output = result.stdout.strip()
            if not output:
                return []

            stylelint_results = json.loads(output)
            for file_result in stylelint_results:
                rel_path = os.path.relpath(file_result["source"], base_dir).replace("\\", "/")
                for warning in file_result.get("warnings", []):
                    severity_str = warning.get("severity", "warning")
                    severity = SeverityLevel.HIGH if severity_str == "error" else SeverityLevel.LOW
                    rule = warning.get("rule", "unknown")
                    text = warning.get("text", "")
                    line = warning.get("line", "?")

                    issues.append(ReviewIssue(
                        file=rel_path,
                        issue=f"Stylelint [{rule}]: {text}",
                        severity=severity,
                        explanation=f"Stylelint rule '{rule}' violation at line {line}: {text}",
                        fix="Fix the CSS according to the Stylelint rule requirements.",
                        recommendation=f"Follow CSS best practices for '{rule}'.",
                        insights="Static analysis finding from Stylelint.",
                        source="static",
                    ))
        except FileNotFoundError:
            logger.info("Stylelint/npx not found, skipping CSS static analysis.")
        except subprocess.TimeoutExpired:
            logger.warning("Stylelint timed out.")
        except json.JSONDecodeError as e:
            logger.warning("Could not parse Stylelint output: %s", e)
        except Exception as e:
            logger.error("Stylelint error: %s", e)
        finally:
            if created_config and os.path.exists(stylelint_config):
                os.remove(stylelint_config)

        return issues

    def run_bandit(self, file_paths: List[str], base_dir: str) -> List[ReviewIssue]:
        """Run Bandit on Python files."""
        py_files = [p for p in file_paths if Path(p).suffix.lower() == ".py"]
        if not py_files:
            return []

        abs_paths = [os.path.join(base_dir, p) for p in py_files]
        issues = []

        try:
            result = subprocess.run(
                ["bandit", "-f", "json", "-q"] + abs_paths,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = result.stdout.strip()
            if not output:
                return []

            bandit_data = json.loads(output)
            for finding in bandit_data.get("results", []):
                rel_path = os.path.relpath(finding["filename"], base_dir).replace("\\", "/")
                sev_str = finding.get("issue_severity", "MEDIUM").upper()
                severity = BANDIT_SEVERITY_MAP.get(sev_str, SeverityLevel.MEDIUM)
                test_id = finding.get("test_id", "")
                test_name = finding.get("test_name", "")
                issue_text = finding.get("issue_text", "")
                line = finding.get("line_number", "?")
                more_info = finding.get("more_info", "")

                issues.append(ReviewIssue(
                    file=rel_path,
                    issue=f"Bandit [{test_id}] {test_name}: {issue_text}",
                    severity=severity,
                    explanation=f"Security issue at line {line}: {issue_text}",
                    fix="Review and remediate this security issue.",
                    recommendation=f"See Bandit docs: {more_info}" if more_info else "Follow Python security best practices.",
                    insights="Security finding from Bandit static analysis.",
                    source="static",
                ))
        except FileNotFoundError:
            logger.info("Bandit not installed, skipping Python security analysis.")
        except subprocess.TimeoutExpired:
            logger.warning("Bandit timed out.")
        except json.JSONDecodeError as e:
            logger.warning("Could not parse Bandit output: %s", e)
        except Exception as e:
            logger.error("Bandit error: %s", e)

        return issues

    def run_all(self, file_paths: List[str], base_dir: str) -> List[ReviewIssue]:
        """Run all available static analyzers and combine results."""
        issues = []
        issues.extend(self.run_eslint(file_paths, base_dir))
        issues.extend(self.run_stylelint(file_paths, base_dir))
        issues.extend(self.run_bandit(file_paths, base_dir))
        logger.info("Static analysis found %d issues", len(issues))
        return issues
