# Skill System Documentation

A dynamic skill discovery and loading system for managed-agentcore that enables agents to load specialized instructions on-demand, inspired by Claude Code's skill architecture.

## Overview

The Skill System allows agents to dynamically discover and load specialized skills (detailed instructions, code examples, best practices) without bloating the system prompt. Skills are loaded lazily—only when needed—reducing token usage and improving response quality.

### Key Benefits

- **Lazy Loading**: Skills loaded on-demand, not at startup
- **Dynamic Discovery**: Auto-detect skills from directory structure
- **Modular Design**: Add new skills without code changes
- **Token Efficient**: Only active skills consume context tokens
- **No Caching**: Always reads latest file content for rapid development
- **Graceful Degradation**: Missing skills don't crash the runtime

### Design Principles

1. **Minimal Startup Impact**: Skill discovery completes in <1 second for 100 skills
2. **Zero Caching**: Always read latest file content for development flexibility
3. **Docker Compatible**: Works in containerized Fargate environment
4. **Comprehensive Logging**: Full observability for debugging

## Architecture Overview

The skill system consists of four main components that work together to provide on-demand skill loading:

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    AgentCore Runtime Startup                    │
│                                                                 │
│  1. initialize_skills(["./skills"])                            │
│     │                                                           │
│     ├─→ 2. SkillDiscovery.discover()                          │
│     │      - Scan directories recursively                      │
│     │      - Find all SKILL.md files                           │
│     │      - Parse YAML frontmatter only                       │
│     │      - Return: {skill_name: {description, path, ...}}   │
│     │                                                           │
│     ├─→ 3. SkillLoader(available_skills)                      │
│     │      - Store skill metadata                              │
│     │      - Ready for lazy loading                            │
│     │                                                           │
│     ├─→ 4. setup_skill_tool(loader, available_skills)         │
│     │      - Configure skill_tool                              │
│     │      - Update TOOL_SPEC with skill list                  │
│     │                                                           │
│     └─→ 5. generate skill_prompt                               │
│            - Create <skill_instructions> section               │
│            - Create <available_skills> list                    │
│                                                                 │
│  6. Append skill_prompt to agent system prompts                │
│  7. Add skill_tool to agent tools list                         │
│  8. Build agent graph and start runtime                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Runtime Execution (Lazy Loading)             │
│                                                                 │
│  User Query: "Evaluate this short-form drama script"           │
│     │                                                           │
│     ├─→ Agent sees 'shortform-script-evaluator' in            │
│     │   <available_skills> section of system prompt            │
│     │                                                           │
│     ├─→ Agent invokes:                                         │
│     │   skill_tool(skill_name="shortform-script-evaluator")   │
│     │                                                           │
│     ├─→ skill_tool calls loader.load("shortform-script-...")  │
│     │                                                           │
│     ├─→ SkillLoader reads full SKILL.md from disk             │
│     │   (no caching - always fresh content)                    │
│     │                                                           │
│     ├─→ skill_tool wraps content in XML:                       │
│     │   <skill name='...'>...full content...</skill>          │
│     │                                                           │
│     └─→ Agent receives skill instructions and follows them     │
│         to complete the task                                    │
└─────────────────────────────────────────────────────────────────┘
```

### How Skill Discovery Works

**SkillDiscovery Class** (`src/utils/skills/discovery.py`)

The discovery process scans skill directories at startup to build a metadata catalog:

1. **Recursive Scanning**: Uses `Path.rglob("SKILL.md")` to find all SKILL.md files in nested directories
2. **Frontmatter Parsing**: Extracts only YAML frontmatter (not full content) using regex and `yaml.safe_load()`
3. **Metadata Extraction**: Collects `name`, `description`, and optional fields (`license`, `allowed-tools`)
4. **Validation**: Checks for required fields and logs warnings for malformed files
5. **Duplicate Detection**: Warns if multiple skills have the same name, keeps first occurrence
6. **Result**: Returns dictionary mapping skill names to metadata

**Performance**: Completes in <1 second for 100 skills because it only reads frontmatter, not full content.

### How Skill Loading Works

**SkillLoader Class** (`src/utils/skills/loader.py`)

The loader provides lazy, on-demand loading of full skill content:

1. **Initialization**: Stores skill metadata from discovery (paths, descriptions)
2. **Load on Demand**: When `load(skill_name)` is called, reads full SKILL.md file from disk
3. **No Caching**: Each load operation reads from file system (enables rapid development)
4. **Error Handling**: Raises `SkillNotFoundError` with helpful message if skill doesn't exist
5. **Logging**: Logs skill name, path, and content length for observability

**Design Rationale**: No caching allows developers to edit skills and see changes immediately without restarting the runtime.

### How Skills Integrate with Agents

**Integration Points**:

1. **skill_tool** (`src/tools/skill_tool.py`): Strands SDK-compatible tool that agents can invoke
2. **System Prompt Augmentation**: `skill_prompt` added to agent system prompts with:
   - `<skill_instructions>`: How to use skills
   - `<available_skills>`: List of discovered skills with descriptions
3. **Tool Registration**: `skill_tool` added to agent tools list during graph building

**Agent Workflow**:

1. Agent receives user query
2. Agent sees available skills in system prompt
3. Agent decides which skill (if any) is relevant
4. Agent invokes `skill_tool(skill_name="...")`
5. Tool loads full skill content and returns it wrapped in XML
6. Agent follows skill instructions to complete task

### Lazy Loading Design and Benefits

**Why Lazy Loading?**

- **Startup Performance**: Discovery only reads frontmatter (~100 bytes per skill), not full content (10-100KB per skill)
- **Memory Efficiency**: Only active skills consume memory during execution
- **Token Efficiency**: Only invoked skills consume context tokens
- **Development Flexibility**: No caching means instant updates when editing skills

**Trade-offs**:

- Small I/O cost when loading skill (typically <100ms for 100KB file)
- Acceptable because skills are loaded infrequently (once per task type)
- File system reads are fast on modern SSDs and in-container storage

## Components

The skill system consists of four main Python modules:

### 1. Skill Discovery (`src/utils/skills/discovery.py`)

**Purpose**: Scan skill directories and extract metadata from SKILL.md files without loading full content.

**Class**: `SkillDiscovery`

**Key Methods**:

```python
class SkillDiscovery:
    def __init__(self, skill_dirs: list[str]):
        """Initialize with list of directories to scan."""
        
    def discover(self) -> dict[str, dict]:
        """
        Scan all skill directories and return metadata.
        
        Returns:
            {
                "skill_name": {
                    "description": "Brief description",
                    "path": "/absolute/path/to/SKILL.md",
                    "metadata": {name, description, license, allowed-tools}
                }
            }
        """
```

**Features**:

- Recursive directory scanning using `Path.rglob("SKILL.md")`
- YAML frontmatter parsing with `yaml.safe_load()`
- Duplicate skill detection and warnings
- Graceful error handling for malformed files
- Supports nested directory structures (e.g., `skills/document-skills/pdf/SKILL.md`)

**Usage**:

```python
from src.utils.skills.discovery import SkillDiscovery

discovery = SkillDiscovery(skill_dirs=["./skills"])
available_skills = discovery.discover()
# Returns: {'pdf': {'description': '...', 'path': '...', 'metadata': {...}}, ...}
```

### 2. Skill Loader (`src/utils/skills/loader.py`)

**Purpose**: Lazily load full skill content when invoked (no caching).

**Class**: `SkillLoader`

**Key Methods**:

```python
class SkillLoader:
    def __init__(self, available_skills: dict[str, dict]):
        """Initialize with skill metadata from discovery."""
        
    def load(self, skill_name: str) -> str:
        """
        Load full SKILL.md content (no caching).
        
        Args:
            skill_name: Name of skill to load
            
        Returns:
            Full file content including frontmatter
            
        Raises:
            SkillNotFoundError: If skill doesn't exist
        """
        
    def skill_exists(self, skill_name: str) -> bool:
        """Check if skill exists without loading."""
        
    def get_skill_description(self, skill_name: str) -> str:
        """Get description without loading full content."""
```

**Features**:

- No caching: Always reads from file system for latest content
- Clear error messages for missing skills
- Minimal memory footprint
- Logs skill name, path, and content length on each load

**Usage**:

```python
from src.utils.skills.loader import SkillLoader

loader = SkillLoader(available_skills)
content = loader.load("shortform-script-evaluator")  # Returns full SKILL.md content
```

### 3. Skill Tool (`src/tools/skill_tool.py`)

**Purpose**: Strands SDK-compatible tool for agent skill invocation.

**Key Functions**:

```python
def setup_skill_tool(loader: SkillLoader, available_skills: dict[str, dict]):
    """
    Initialize skill tool with loader and update TOOL_SPEC.
    Updates TOOL_SPEC description to include available skills list.
    """

def handle_skill_tool(skill_name: str) -> str:
    """
    Load skill and return formatted content.
    
    Returns:
        <skill name='skill_name'>
        [full SKILL.md content]
        </skill>
        
        The skill 'skill_name' has been loaded.
        Follow the instructions above to complete the task.
    """

def skill_tool(tool: ToolUse, **kwargs) -> ToolResult:
    """
    Strands SDK wrapper.
    Returns ToolResult with status "success" or "error".
    """
```

**TOOL_SPEC**:

```python
TOOL_SPEC = {
    "name": "skill_tool",
    "description": "Load specialized skill instructions...",
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Name of the skill to invoke"
                }
            },
            "required": ["skill_name"]
        }
    }
}
```

**Features**:

- Wraps content in XML tags for clear LLM parsing
- Appends usage instruction after skill content
- Returns error ToolResult on failure (doesn't crash)
- Updates description dynamically with available skills

### 4. Skill Utils (`src/utils/skills/skill_utils.py`)

**Purpose**: Orchestrate skill system initialization and generate system prompt.

**Key Functions**:

```python
def initialize_skills(
    skill_dirs: list[str] = None,
    verbose: bool = False
) -> Tuple[dict, str]:
    """
    Initialize complete skill system.
    
    Args:
        skill_dirs: Directories to scan (default: ["./skills"])
        verbose: Print initialization progress
        
    Returns:
        (available_skills, skill_prompt) tuple
    """

def get_skill_prompt(available_skills: dict[str, dict]) -> str:
    """
    Generate system prompt section for skills.
    
    Returns Markdown + XML hybrid format with:
    - <skill_instructions> explaining how to use skills
    - <available_skills> listing all discovered skills
    """
```

**Initialization Flow**:

1. Create `SkillDiscovery` and call `discover()`
2. Create `SkillLoader` with discovered skills
3. Call `setup_skill_tool(loader, available_skills)`
4. Generate skill prompt with `get_skill_prompt()`
5. Return tuple for runtime use

**Features**:

- Returns empty dict and empty string if no skills found
- Prints progress if verbose=True
- Logs skill count and names at INFO level
- Never raises exceptions (graceful degradation)

**Usage**:

```python
from src.utils.skills.skill_utils import initialize_skills

available_skills, skill_prompt = initialize_skills(
    skill_dirs=["./skills"],
    verbose=True
)

# Append to your base prompt
system_prompt = base_prompt + skill_prompt
```

## SKILL.md Format Specification

Each skill is defined by a `SKILL.md` file with YAML frontmatter followed by markdown content.

### File Structure

```markdown
---
name: skill-identifier
description: >
  Brief description of what this skill does and when to use it.
  Can be multi-line using YAML's > syntax.
license: MIT
allowed-tools:
  - tool_name_1
  - tool_name_2
---

# Skill Title

## Overview
High-level explanation of the skill's purpose...

## Quick Start
Minimal example to get started...

## Detailed Instructions
Comprehensive guidance with code examples...

## Best Practices
Tips and recommendations...

## Common Pitfalls
What to avoid...
```

### YAML Frontmatter Requirements

The frontmatter is enclosed between `---` delimiters and must be valid YAML.

#### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `name` | string | Unique skill identifier used in `skill_tool(skill_name="...")`. Must be alphanumeric with hyphens only. | `pdf`, `shortform-script-evaluator` |
| `description` | string | Brief explanation shown in available skills list. Should clearly indicate when to use this skill. | `Comprehensive PDF manipulation toolkit for extracting text and tables` |

#### Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `license` | string | License information for the skill content | `MIT`, `Apache-2.0` |
| `allowed-tools` | array | List of tools this skill may use (informational only, not enforced) | `[readFile, executeBash]` |

### Markdown Content Structure

The content after the frontmatter should be well-structured markdown:

#### Recommended Sections

1. **Overview**: High-level explanation of what the skill does
2. **Quick Start**: Minimal working example to get started quickly
3. **Detailed Instructions**: Comprehensive step-by-step guidance
4. **Code Examples**: Concrete examples with code blocks
5. **Best Practices**: Tips and recommendations
6. **Common Pitfalls**: What to avoid
7. **Troubleshooting**: Common issues and solutions (if applicable)

#### Content Guidelines

- **Be Specific**: Provide concrete examples, not abstract descriptions
- **Use Code Blocks**: Include working code examples with proper syntax highlighting
- **Structure with Headers**: Use `##` and `###` for clear navigation
- **Keep Focused**: One skill per domain/task type
- **Write for Agents**: Remember that LLMs will read and follow these instructions
- **Include Context**: Explain when and why to use specific approaches

### Reference File Syntax

Skills can reference external files using the `#[[file:...]]` syntax:

```markdown
## Reference Files

- **`references/criteria-synthesized.md`** — Detailed scoring rubric
- Use this file when you need specific numerical thresholds
```

**Note**: The current implementation does not automatically load reference files. This is a placeholder for future enhancement.

### Real-World Example

Here's an excerpt from the `shortform-script-evaluator` skill:

```markdown
---
name: shortform-script-evaluator
description: >
  숏폼 드라마 대본 평가 전문 스킬. 반드시 사용해야 하는 상황:
  사용자가 숏폼 드라마 대본(텍스트/PDF/파일)을 제시하고 평가·채점·피드백·검토를 요청할 때,
  대본의 숏폼 적합성 판단을 요청할 때, 대본이 통할지 / 강점·약점·개선방향을 묻거나
  "이 대본 어때?"라고 물을 때. 59편 논문 기반 누적 DB를 적용한 심층 평가 보고서를
  한국어로 제공. 대본·시나리오·스크립트·원고 관련 평가 요청에 항상 이 스킬 사용.
license: MIT
allowed-tools:
  - readFile
  - readMultipleFiles
  - executeBash
---

# 숏폼 드라마 대본 평가 스킬

## 역할

59편 중국·한국 숏폼 드라마 학술 논문에서 추출·정제된 판별 기준을 적용해
대본을 심층 평가하고 100점 만점 점수와 개선 제안을 제공합니다.

모든 평가 결과는 **한국어**로 제공합니다.
중문 원어 용어는 \`한국어 (中文原文)\` 형식으로 첫 등장 시 병기합니다.

---

## 0단계: 대본 파일 처리

**기본 원칙: 대본 전체를 반드시 읽는다. 임의로 샘플링하지 않는다.**

숏폼 드라마는 화당 3~10분 분량이므로 전체 읽기가 가능하고 필수다.
클리프행어·복선·실패 패턴은 특정 화에만 나타날 수 있어 샘플링 시 오평가 발생.

- **텍스트 직접 입력** → 전체 읽기
- **PDF 파일** → \`pdftotext -layout <file> /tmp/script.txt\` 후 전체 읽기
- **파일 읽기 실패(스캔본)** → \`pdftoppm -jpeg -r 150\` 래스터화 후 전체 시각 분석
...
```

This example demonstrates:

- Multi-line description using YAML `>` syntax
- Clear indication of when to use the skill
- Structured sections with step-by-step instructions
- Specific tool usage examples
- Domain-specific terminology and guidelines

### Validation Rules

The skill system validates SKILL.md files during discovery:

1. **YAML Syntax**: Must be valid YAML between `---` delimiters
2. **Required Fields**: Must have `name` and `description`
3. **Name Format**: Should contain only alphanumeric characters and hyphens
4. **Encoding**: Must be UTF-8 encoded

**Error Handling**:

- Invalid YAML: Logged as error, skill skipped
- Missing required fields: Logged as warning, skill skipped
- Duplicate names: Logged as warning, first occurrence kept
- File read errors: Logged as error, skill skipped

The runtime continues even if some skills fail validation (graceful degradation).

## Directory Structure

Skills are organized in a hierarchical directory structure:

```
managed-agentcore/
├── skills/                                    # Root skills directory
│   ├── shortform-script-evaluator/           # Skill directory
│   │   ├── SKILL.md                          # Skill definition (required)
│   │   └── references/                       # Optional reference files
│   │       └── criteria-synthesized.md
│   ├── document-skills/                      # Nested organization
│   │   ├── pdf/
│   │   │   └── SKILL.md
│   │   ├── docx/
│   │   │   └── SKILL.md
│   │   └── xlsx/
│   │       └── SKILL.md
│   └── template-skill/                       # Template for new skills
│       └── SKILL.md
├── src/
│   ├── utils/
│   │   └── skills/                           # Skill system implementation
│   │       ├── __init__.py
│   │       ├── discovery.py                  # Skill discovery
│   │       ├── loader.py                     # Lazy loading
│   │       └── skill_utils.py                # Initialization
│   └── tools/
│       └── skill_tool.py                     # Strands SDK tool
└── agentcore_runtime.py                      # Runtime integration
```

**Key Points**:

- Each skill must have its own directory with a `SKILL.md` file
- Nested directories are fully supported (e.g., `document-skills/pdf/`)
- Reference files can be placed alongside SKILL.md (not auto-loaded yet)
- The discovery process scans recursively for all `SKILL.md` files

**Naming Conventions**:

- Skill directories: lowercase with hyphens (e.g., `shortform-script-evaluator`)
- Skill names in frontmatter: match directory name or use descriptive identifier
- Reference files: any structure, referenced in SKILL.md content

## Integration with AgentCore Runtime

### Runtime Integration (`agentcore_runtime.py`)

The skill system is initialized at runtime startup before building the agent graph:

```python
# At module level (before app.entrypoint)
from src.utils.skills.skill_utils import initialize_skills

# Global variables for skill system
_available_skills = {}
_skill_prompt = ""

# In main execution block (before app.run())
if __name__ == "__main__":
    # Initialize skill system before starting runtime
    try:
        _available_skills, _skill_prompt = initialize_skills(
            skill_dirs=["./skills"],
            verbose=True
        )
        if _available_skills:
            print(f"✅ Skill system initialized with {len(_available_skills)} skills")
        else:
            print("⚠️ No skills discovered - skill system disabled")
    except Exception as e:
        print(f"⚠️ Skill system initialization failed: {e}")
        print("Continuing without skill system...")
    
    # Register cleanup and run
    atexit.register(cleanup_fargate_session)
    app.run()
```

### Agent Node Integration (`src/graph/nodes.py`)

Skills are integrated into agent nodes by:

1. Importing skill_tool
2. Importing skill_prompt from runtime
3. Augmenting agent system prompt
4. Adding skill_tool to agent tools

```python
# At module level
from src.tools.skill_tool import skill_tool

# In agent creation (e.g., supervisor_node, coder_node, reporter_node)
def supervisor_node(task=None, **kwargs):
    # ... existing code ...
    
    # Import skill prompt from runtime
    from agentcore_runtime import _skill_prompt
    
    # Augment system prompt
    base_prompt = apply_prompt_template("supervisor", task)
    system_prompt = base_prompt + _skill_prompt
    
    # Create agent with skill_tool
    agent = strands_utils.get_agent(
        agent_name="supervisor",
        system_prompts=system_prompt,
        tools=[
            tracker_agent_tool,
            skill_tool,  # Add skill_tool
            # ... other tools ...
        ],
        streaming=True
    )
    
    return agent
```

### Complete Usage Example

Here's a complete example showing how to integrate the skill system:

**Step 1: Initialize skill system in runtime**

```python
# agentcore_runtime.py
from src.utils.skills.skill_utils import initialize_skills
from src.tools.skill_tool import skill_tool

# Initialize at startup
_available_skills, _skill_prompt = initialize_skills(
    skill_dirs=["./skills"],
    verbose=True
)

print(f"Discovered skills: {list(_available_skills.keys())}")
```

**Step 2: Augment agent system prompts**

```python
# src/graph/nodes.py
from agentcore_runtime import _skill_prompt

def create_agent(agent_name, base_prompt, tools):
    # Append skill prompt to base prompt
    system_prompt = base_prompt + _skill_prompt
    
    # Create agent with skill_tool in tools list
    agent = strands_utils.get_agent(
        agent_name=agent_name,
        system_prompts=system_prompt,
        tools=[skill_tool] + tools,
        streaming=True
    )
    
    return agent
```

**Step 3: Agent uses skills at runtime**

When a user asks a question that requires specialized knowledge:

```
User: "Please evaluate this short-form drama script"

Agent (internal reasoning):
- Sees 'shortform-script-evaluator' in <available_skills>
- Recognizes this matches the user's request
- Invokes: skill_tool(skill_name="shortform-script-evaluator")

skill_tool response:
<skill name='shortform-script-evaluator'>
---
name: shortform-script-evaluator
description: 숏폼 드라마 대본 평가 전문 스킬...
---
# 숏폼 드라마 대본 평가 스킬
[...full skill content...]
</skill>

The skill 'shortform-script-evaluator' has been loaded.
Follow the instructions above to complete the task.

Agent: [Follows skill instructions to evaluate the script]
```

### System Prompt Generation

The `initialize_skills()` function generates a prompt section like:

```markdown
## Skill System

<skill_instructions>
You have access to specialized skills that provide detailed guidance for specific tasks.
Use skill_tool to load relevant skill instructions when working on specialized tasks.

How to use skills:
- Invoke skills using skill_tool with the skill name
- The skill's prompt will expand and provide detailed instructions
- Follow the loaded skill instructions precisely to complete the task

Important:
- Only use skills listed in <available_skills> below
- Do not invoke a skill that is already loaded in the current conversation
- Skills provide code examples, best practices, and domain-specific guidance
</skill_instructions>

<available_skills>
  - shortform-script-evaluator: 숏폼 드라마 대본 평가 전문 스킬. 반드시 사용해야 하는 상황: 사용자가 숏폼 드라마 대본(텍스트/PDF/파일)을 제시하고 평가·채점·피드백·검토를 요청할 때...
  - pdf: Comprehensive PDF manipulation toolkit for extracting text and tables...
  - docx: Microsoft Word document processing and generation...
</available_skills>
```

This prompt section:

- Explains how to use skills
- Lists all available skills with descriptions
- Helps agents decide when to invoke skills
- Provides clear usage guidelines

## Creating New Skills

Follow these steps to create a new skill:

### Step 1: Create Skill Directory

```bash
cd managed-agentcore/skills
mkdir my-new-skill
cd my-new-skill
```

### Step 2: Create SKILL.md File

Create `SKILL.md` with valid YAML frontmatter and markdown content:

```markdown
---
name: my-new-skill
description: >
  Brief description of what this skill does and when to use it.
  Be specific about the use cases so agents know when to invoke it.
license: MIT
allowed-tools:
  - readFile
  - executeBash
---

# My New Skill

## Overview

Explain what this skill helps with and why it exists.

## When to Use This Skill

- Use case 1: When the user asks for X
- Use case 2: When you need to do Y
- Use case 3: When working with Z

## Quick Start

Provide a minimal working example:

\`\`\`python
# Example code
def example():
    pass
\`\`\`

## Detailed Instructions

### Step 1: First Step

Explain the first step in detail...

### Step 2: Second Step

Explain the second step in detail...

## Code Examples

### Example 1: Basic Usage

\`\`\`python
# Concrete example with explanation
\`\`\`

### Example 2: Advanced Usage

\`\`\`python
# More complex example
\`\`\`

## Best Practices

- Best practice 1
- Best practice 2
- Best practice 3

## Common Pitfalls

- Pitfall 1: What to avoid and why
- Pitfall 2: Common mistake and solution
- Pitfall 3: Edge case to watch for

## Troubleshooting

**Problem**: Common issue

**Solution**: How to fix it
```

### Step 3: Test the Skill

Restart the runtime to discover the new skill:

```bash
# If running locally
python agentcore_runtime.py

# If running in Docker
docker build -t agentcore .
docker run agentcore
```

Check the logs for:

```
Discovered 4 skills: ['shortform-script-evaluator', 'pdf', 'docx', 'my-new-skill']
✅ Skill system initialized with 4 skills
```

### Step 4: Test Skill Invocation

Test that the skill can be loaded:

```python
from src.tools.skill_tool import skill_tool

result = skill_tool({
    'toolUseId': 'test-123',
    'input': {'skill_name': 'my-new-skill'}
})

assert result['status'] == 'success'
print(result['content'][0]['text'])
```

### Step 5: Refine Description

Based on testing, refine the skill description to make it clearer when agents should use it:

```yaml
description: >
  Use this skill when the user explicitly asks to [specific action].
  Applies [specific methodology] for [specific outcome].
  Keywords: [keyword1], [keyword2], [keyword3]
```

### Best Practices for Skill Creation

1. **Clear Description**: Write descriptions that clearly indicate when to use the skill
   - Good: "Use when user asks to evaluate short-form drama scripts"
   - Bad: "Script evaluation skill"

2. **Concrete Examples**: Include working code examples, not pseudocode
   - Agents perform better with concrete examples they can adapt

3. **Structured Content**: Use headers (`##`, `###`) for clear navigation
   - Agents can better parse and follow structured instructions

4. **Step-by-Step Instructions**: Break complex tasks into numbered steps
   - Makes it easier for agents to follow the process

5. **Domain-Specific Terminology**: Use precise terminology from the domain
   - Helps agents understand the context and requirements

6. **Error Handling**: Include common errors and how to handle them
   - Reduces agent confusion when things go wrong

7. **Keep Skills Focused**: One skill per domain/task type
   - Easier to maintain and use than monolithic skills

8. **Test with Real Queries**: Test the skill with actual user queries
   - Ensures the skill is practical and useful

### Skill Template

Use the template skill as a starting point:

```bash
cp -r skills/template-skill skills/my-new-skill
cd skills/my-new-skill
# Edit SKILL.md with your content
```

## Available Skills

The managed-agentcore implementation currently includes:

### shortform-script-evaluator

**Purpose**: Evaluate short-form drama scripts using research-based criteria

**When to use**:

- User provides a short-form drama script (text/PDF/file) and asks for evaluation
- User asks for scoring, feedback, or review of a script
- User asks "Is this script good?" or "What are the strengths/weaknesses?"

**Features**:

- Applies criteria from 59 academic papers on short-form drama
- Provides 100-point scoring across 5 categories
- Identifies failure patterns and suggests improvements
- Outputs comprehensive evaluation report in Korean

**Example invocation**:

```
User: "Please evaluate this short-form drama script"
Agent: [Invokes skill_tool(skill_name="shortform-script-evaluator")]
Agent: [Follows skill instructions to analyze script and provide detailed report]
```

### Future Skills

Additional skills can be added for:

- PDF processing (extraction, manipulation, forms)
- Document processing (Word, Excel, PowerPoint)
- Web scraping and data extraction
- Code analysis and refactoring
- Testing and quality assurance
- Deployment and infrastructure
- Domain-specific tasks (legal, medical, financial, etc.)

## Deployment Considerations

### Docker Integration

The skill system works seamlessly in Docker containers:

**Dockerfile**:

```dockerfile
# Copy skill infrastructure
COPY src/utils/skills/ /app/src/utils/skills/
COPY src/tools/skill_tool.py /app/src/tools/

# Copy skills directory
COPY skills/ /app/skills/

# Ensure skills directory exists (even if empty)
RUN mkdir -p /app/skills
```

**File paths**: Skills are resolved relative to the container's working directory (`/app`)

### Fargate Deployment

The skill system is compatible with AWS Fargate:

- **Startup Impact**: <2 seconds total (well within acceptable limits)
- **Memory Usage**: <10MB for skill metadata (100 skills)
- **No Network Required**: All skill operations are local file I/O
- **Container Image**: Skills are part of the container image (not mounted volumes)

**Limitations**:

- Skills cannot be updated without rebuilding the container image
- No dynamic skill addition at runtime
- For development: mount skills directory as volume for rapid iteration

### CloudWatch Logging

The skill system provides comprehensive logging for production monitoring:

**Log Levels**:

- **INFO**: Successful operations, skill counts, skill loading
- **WARNING**: Missing directories, no skills found, duplicate skills
- **ERROR**: YAML parsing errors, file read failures

**Example logs**:

```
INFO: Discovered 3 skills: ['shortform-script-evaluator', 'pdf', 'docx']
INFO: Skill tool initialized with 3 skills
✅ Skill system initialized with 3 skills

INFO: Loading skill: shortform-script-evaluator
INFO: Loaded skill 'shortform-script-evaluator' from /app/skills/shortform-script-evaluator/SKILL.md (15234 chars)

WARNING: Skill directory not found: /app/skills-extra
WARNING: Duplicate skill 'pdf' found. Keeping: /app/skills/pdf/SKILL.md, Ignoring: /app/skills/pdf-v2/SKILL.md

ERROR: YAML parsing error in /app/skills/broken/SKILL.md: mapping values are not allowed here
```

### Performance Characteristics

**Startup Performance**:

- Skill discovery: <1 second for 100 skills
- Loader initialization: <10ms
- Tool setup: <10ms
- Prompt generation: <100ms
- **Total impact**: <2 seconds

**Runtime Performance**:

- Skill loading: <100ms for 100KB file
- XML wrapping: <1ms
- Tool invocation overhead: <10ms
- **Total latency**: <50ms per skill invocation

**Memory Usage**:

- Skill metadata: ~50KB for 100 skills
- No content caching: Minimal memory footprint
- Per-load memory: Temporary (released after use)

### Environment Variables

No environment variables are required. The skill system uses hardcoded defaults:

- Skill directories: `["./skills"]`
- Verbose logging: `True` (for CloudWatch visibility)

To customize, modify the initialization call in `agentcore_runtime.py`:

```python
_available_skills, _skill_prompt = initialize_skills(
    skill_dirs=["./skills", "./custom-skills"],  # Multiple directories
    verbose=True  # Enable verbose output
)
```

## Key Files and Locations

| File | Purpose | Location |
|------|---------|----------|
| **Skill Discovery** | Scan directories and extract metadata | `src/utils/skills/discovery.py` |
| **Skill Loader** | Lazy loading of full skill content | `src/utils/skills/loader.py` |
| **Skill Utils** | Initialization orchestration | `src/utils/skills/skill_utils.py` |
| **Skill Tool** | Strands SDK tool wrapper | `src/tools/skill_tool.py` |
| **Skills Directory** | Root directory for all skills | `skills/` |
| **Runtime Integration** | Skill system initialization | `agentcore_runtime.py` |
| **Agent Integration** | Tool and prompt augmentation | `src/graph/nodes.py` |

## References

- **Requirements**: `.kiro/specs/skill-system-integration/requirements.md`
- **Design**: `.kiro/specs/skill-system-integration/design.md`
- **Tasks**: `.kiro/specs/skill-system-integration/tasks.md`
- **Example Skill**: `skills/shortform-script-evaluator/SKILL.md`

## Summary

The skill system provides a flexible, efficient way to extend agent capabilities without bloating system prompts:

- **Discovery**: Scans directories at startup, extracts metadata only
- **Loading**: Loads full content on-demand, no caching
- **Integration**: Seamless integration with Strands SDK and AgentCore Runtime
- **Performance**: Minimal startup impact (<2s), fast loading (<100ms)
- **Deployment**: Docker and Fargate compatible
- **Observability**: Comprehensive CloudWatch logging

By following this documentation, you can create, deploy, and maintain skills that enhance agent capabilities for specialized tasks.

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue: No skills discovered

**Symptoms**:

- Log message: `⚠️ No skills discovered - skill system disabled`
- Agent doesn't have access to any skills

**Diagnosis Steps**:

1. Check if `skills/` directory exists:

   ```bash
   ls -la managed-agentcore/skills/
   ```

2. Check if SKILL.md files exist:

   ```bash
   find managed-agentcore/skills/ -name "SKILL.md"
   ```

3. Check CloudWatch logs for warnings:

   ```
   Skill directory not found: /app/skills
   ```

**Solutions**:

- **Missing directory**: Create `skills/` directory at project root
- **Empty directory**: Add at least one skill with valid SKILL.md
- **Wrong location**: Ensure skills are in `./skills/` relative to runtime working directory
- **Docker issue**: Verify `COPY skills/ /app/skills/` in Dockerfile

#### Issue: Skill not loading

**Symptoms**:

- Agent invokes skill_tool but receives error
- Error message: `Skill 'xyz' not found`

**Diagnosis Steps**:

1. Check if skill was discovered:

   ```python
   # In Python console or logs
   print(available_skills.keys())
   ```

2. Verify skill name matches exactly (case-sensitive):

   ```bash
   grep "^name:" skills/*/SKILL.md
   ```

3. Check file path is accessible:

   ```bash
   cat skills/my-skill/SKILL.md
   ```

**Solutions**:

- **Name mismatch**: Skill names are case-sensitive, check exact spelling
- **File deleted**: Skill may have been deleted after discovery, restart runtime
- **Path issue**: Verify file path in available_skills matches actual location
- **Permissions**: Check file permissions allow reading

#### Issue: Skill has invalid YAML frontmatter

**Symptoms**:

- Skill not discovered despite SKILL.md file existing
- Log message: `YAML parsing error in /path/to/SKILL.md`

**Diagnosis Steps**:

1. Check YAML syntax:

   ```bash
   head -n 20 skills/my-skill/SKILL.md
   ```

2. Validate YAML online: Copy frontmatter to https://www.yamllint.com/

3. Check for common YAML errors:
   - Missing closing `---`
   - Incorrect indentation
   - Unquoted special characters
   - Missing required fields

**Solutions**:

- **Missing delimiters**: Ensure frontmatter starts and ends with `---`
- **Indentation**: Use spaces (not tabs), consistent indentation
- **Special characters**: Quote strings with special characters
- **Required fields**: Ensure `name` and `description` are present

**Example of valid frontmatter**:

```yaml
---
name: my-skill
description: Brief description of the skill
license: MIT
allowed-tools:
  - tool1
  - tool2
---
```

#### Issue: Agent not using skills

**Symptoms**:

- Skills are discovered and loaded successfully
- Agent doesn't invoke skill_tool even when appropriate

**Diagnosis Steps**:

1. Check if skill_tool is in agent's tools list:

   ```python
   # In agent configuration
   print([tool.TOOL_SPEC['name'] for tool in agent_tools])
   ```

2. Check if system prompt includes skill information:

   ```python
   print("<available_skills>" in system_prompt)
   ```

3. Review skill description clarity:

   ```bash
   grep "^description:" skills/*/SKILL.md
   ```

**Solutions**:

- **Missing tool**: Add `skill_tool` to agent's tools list in graph builder
- **Missing prompt**: Ensure `skill_prompt` is appended to agent system prompt
- **Unclear description**: Rewrite skill description to clearly indicate when to use it
- **Agent behavior**: Agent may not recognize the need for the skill, improve description

**Example of clear description**:

```yaml
description: >
  Use this skill when the user asks to evaluate, review, or provide feedback
  on short-form drama scripts. Applies 59-paper research database for scoring.
```

#### Issue: Skill content not updating

**Symptoms**:

- Edited SKILL.md file but agent still uses old content
- Changes not reflected in skill output

**Diagnosis Steps**:

1. Verify file was actually saved:

   ```bash
   cat skills/my-skill/SKILL.md | head -n 30
   ```

2. Check if caching is disabled (should be by default):

   ```python
   # In loader.py, verify no caching logic exists
   ```

**Solutions**:

- **File not saved**: Ensure file was saved after editing
- **Wrong file**: Verify editing the correct SKILL.md file
- **Restart needed**: Restart runtime to re-discover skills (only needed if frontmatter changed)
- **Docker rebuild**: If running in Docker, rebuild image to include updated files

**Note**: The loader has no caching, so content changes should be reflected immediately without restart (unless frontmatter changed).

### Debugging Skill Discovery

To debug skill discovery issues, enable verbose logging:

```python
# In agentcore_runtime.py
available_skills, skill_prompt = initialize_skills(
    skill_dirs=["./skills"],
    verbose=True  # Enable verbose output
)
```

This will print:

```
Discovered 3 skills: ['shortform-script-evaluator', 'pdf', 'docx']
✅ Skill system initialized with 3 skills
```

### CloudWatch Log Patterns

When troubleshooting in production, look for these log patterns:

**Successful initialization**:

```
INFO: Discovered 5 skills: ['skill1', 'skill2', 'skill3', 'skill4', 'skill5']
INFO: Skill tool initialized with 5 skills
✅ Skill system initialized with 5 skills
```

**Discovery warnings**:

```
WARNING: Skill directory not found: /app/skills
WARNING: No YAML frontmatter found in /app/skills/broken/SKILL.md
WARNING: Invalid SKILL.md (missing name or description): /app/skills/incomplete/SKILL.md
WARNING: Duplicate skill 'pdf' found. Keeping: /app/skills/pdf/SKILL.md, Ignoring: /app/skills/pdf-v2/SKILL.md
```

**Loading errors**:

```
ERROR: YAML parsing error in /app/skills/broken/SKILL.md: ...
ERROR: Error reading /app/skills/missing/SKILL.md: [Errno 2] No such file or directory
WARNING: Skill not found: nonexistent-skill
```

**Skill usage**:

```
INFO: Loading skill: shortform-script-evaluator
INFO: Loaded skill 'shortform-script-evaluator' from /app/skills/shortform-script-evaluator/SKILL.md (15234 chars)
```

### Verifying Skills Are Loaded Correctly

To verify skills are working end-to-end:

1. **Check discovery**:

   ```bash
   # Look for discovery log in CloudWatch or console
   grep "Discovered.*skills" logs/agentcore.log
   ```

2. **Check tool registration**:

   ```python
   # In agent code
   assert any(tool.TOOL_SPEC['name'] == 'skill_tool' for tool in agent_tools)
   ```

3. **Check prompt augmentation**:

   ```python
   # In agent code
   assert '<available_skills>' in system_prompt
   assert 'shortform-script-evaluator' in system_prompt
   ```

4. **Test skill invocation**:

   ```python
   # Manually invoke skill_tool
   from src.tools.skill_tool import skill_tool
   
   result = skill_tool({
       'toolUseId': 'test-123',
       'input': {'skill_name': 'shortform-script-evaluator'}
   })
   
   assert result['status'] == 'success'
   assert '<skill name=' in result['content'][0]['text']
   ```

### Performance Issues

#### Issue: Slow startup time

**Diagnosis**:

- Check number of skills: `ls -d skills/*/ | wc -l`
- Check skill file sizes: `du -sh skills/*/SKILL.md`

**Solutions**:

- Reduce number of skills (target: <100 skills)
- Split large skills into smaller, focused skills
- Remove unused skills

**Expected performance**: <1 second for 100 skills, <2 seconds total startup impact

#### Issue: Slow skill loading

**Diagnosis**:

- Check skill file size: `wc -c skills/my-skill/SKILL.md`
- Check disk I/O performance

**Solutions**:

- Reduce skill file size (target: <100KB per skill)
- Split large skills into multiple smaller skills
- Optimize markdown content (remove unnecessary sections)

**Expected performance**: <100ms to load 100KB skill file

### Getting Help

If you encounter issues not covered here:

1. **Check logs**: Review CloudWatch logs for error messages
2. **Verify setup**: Follow the "Verifying Skills Are Loaded Correctly" section
3. **Test components**: Test discovery, loading, and tool invocation separately
4. **Simplify**: Create a minimal test skill to isolate the issue
5. **Report**: Include logs, skill file, and reproduction steps when reporting issues
