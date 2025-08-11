## Development Context & Workflow

### Architecture
This is a **Career Jobs App** using a hybrid development approach:
- **Cursor IDE (local)**: Code exploration, git management, Claude Code integration
- **Daytona sandbox (remote)**: Secure development environment with Claude Code CLI
- **GitHub**: Version control and CI/CD
- **CodeRabbit**: Automated PR reviews

### Development Workflow
1. **Code Exploration**: Use Cursor IDE with Claude Code for understanding codebase structure
2. **Development Work**: Run `make dev` → Install Claude Code in Daytona sandbox → Use `claude` command for actual development
3. **Testing**: Run tests in Daytona environment (isolated execution)
4. **Git Operations**: Use Cursor's git UI for commits/PRs, sync to Daytona with `git pull`

### Key Files & Configuration
- `.daytona.yml`: Sandbox configuration with security policies
- `scripts/dev.sh`: Automated sandbox creation/resumption
- `.env.example`: Template committed to repo
- `.env`: Local (untracked), created from .env.example; contains `DAYTONA_API_KEY`, `GH_PAT`, `ANTHROPIC_API_KEY`
- `Makefile`: `make dev`, `make stop`, `make prune` commands

### Security Considerations
- All code execution happens in isolated Daytona sandbox
- API keys are properly scoped (fine-grained GitHub PAT, repo-only access)
- Environment variables (GH_PAT, ANTHROPIC_API_KEY) are securely injected via .daytona.yml
- Claude Code installation uses secure method (download + verify, not curl | sh)
- Network policies restrict egress to necessary domains only
- `.gitignore` prevents accidental commit of secrets and Claude files

### Claude Code Usage Guidelines
- **In Cursor**: Use for code exploration, understanding, and planning (`Cmd/Ctrl + L`, `Cmd/Ctrl + I`)
- **In Daytona**: Use for actual development work, file modifications, testing, execution
- **Memory**: Use "Add to CLAUDE.md" in Cursor to save important context for future sessions

## Development Challenges

