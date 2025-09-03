"""
Tool processing utilities
"""

import json
import re
import time
from typing import Dict, List, Optional, Any

from app.core.config import settings


def generate_tool_prompt(tools: List[Dict[str, Any]]) -> str:
    """Generate tool injection prompt with enhanced formatting"""
    if not tools:
        return ""
    
    tool_definitions = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
            
        function_spec = tool.get("function", {}) or {}
        function_name = function_spec.get("name", "unknown")
        function_description = function_spec.get("description", "")
        parameters = function_spec.get("parameters", {}) or {}
        
        # Create structured tool definition
        tool_info = [f"## {function_name}", f"**Purpose**: {function_description}"]
        
        # Add parameter details
        parameter_properties = parameters.get("properties", {}) or {}
        required_parameters = set(parameters.get("required", []) or [])
        
        if parameter_properties:
            tool_info.append("**Parameters**:")
            for param_name, param_details in parameter_properties.items():
                param_type = (param_details or {}).get("type", "any")
                param_desc = (param_details or {}).get("description", "")
                requirement_flag = "**Required**" if param_name in required_parameters else "*Optional*"
                tool_info.append(f"- `{param_name}` ({param_type}) - {requirement_flag}: {param_desc}")
        
        tool_definitions.append("\n".join(tool_info))
    
    if not tool_definitions:
        return ""
    
    # Build comprehensive tool prompt
    prompt_template = (
        "\n\n# AVAILABLE FUNCTIONS\n" +
        "\n\n---\n".join(tool_definitions) +
        "\n\n# USAGE INSTRUCTIONS\n"
        "When you need to execute a function, respond ONLY with a JSON object containing tool_calls:\n"
        "```json\n"
        "{\n"
        '  "tool_calls": [\n'
        "    {\n"
        '      "id": "call_" + unique_id,\n'
        '      "type": "function",\n'
        '      "function": {\n'
        '        "name": "function_name",\n'
        '        "arguments": {\n'
        '          "param1": "value1"\n'
        '        }\n'
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "```\n"
        "Important: No explanatory text before or after the JSON.\n"
    )
    
    return prompt_template


def process_messages_with_tools(
    messages: List[Dict[str, Any]], 
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Process messages and inject tool prompts"""
    processed: List[Dict[str, Any]] = []
    
    if tools and settings.TOOL_SUPPORT and (tool_choice != "none"):
        tools_prompt = generate_tool_prompt(tools)
        has_system = any(m.get("role") == "system" for m in messages)
        
        if has_system:
            for m in messages:
                if m.get("role") == "system":
                    mm = dict(m)
                    content = mm.get("content", "")
                    if content is None:
                        content = ""
                    mm["content"] = content + tools_prompt
                    processed.append(mm)
                else:
                    processed.append(m)
        else:
            processed = [{"role": "system", "content": "你是一个有用的助手。" + tools_prompt}] + messages
        
        # Add tool choice hints
        if tool_choice in ("required", "auto"):
            if processed and processed[-1].get("role") == "user":
                last = dict(processed[-1])
                content = last.get("content", "")
                if content is None:
                    content = ""
                last["content"] = content + "\n\n请根据需要使用提供的工具函数。"
                processed[-1] = last
        elif isinstance(tool_choice, dict) and tool_choice.get("type") == "function":
            fname = (tool_choice.get("function") or {}).get("name")
            if fname and processed and processed[-1].get("role") == "user":
                last = dict(processed[-1])
                content = last.get("content", "")
                if content is None:
                    content = ""
                last["content"] = content + f"\n\n请使用 {fname} 函数来处理这个请求。"
                processed[-1] = last
    else:
        processed = list(messages)
    
    # Handle tool/function messages
    final_msgs: List[Dict[str, Any]] = []
    for m in processed:
        role = m.get("role")
        if role in ("tool", "function"):
            tool_name = m.get("name", "unknown")
            tool_content = m.get("content", "")
            if isinstance(tool_content, dict):
                tool_content = json.dumps(tool_content, ensure_ascii=False)
            elif tool_content is None:
                tool_content = ""
            
            # 确保内容不为空且不包含 None
            content = f"工具 {tool_name} 返回结果:\n```json\n{tool_content}\n```"
            if not content.strip():
                content = f"工具 {tool_name} 执行完成"
                
            final_msgs.append({
                "role": "assistant",
                "content": content,
            })
        else:
            final_msgs.append(m)
    
    return final_msgs


# Tool Extraction Patterns
TOOL_CALL_FENCE_PATTERN = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
TOOL_CALL_INLINE_PATTERN = re.compile(r"(\{[^{}]{0,10000}\"tool_calls\".*?\})", re.DOTALL)
FUNCTION_CALL_PATTERN = re.compile(r"调用函数\s*[：:]\s*([\w\-\.]+)\s*(?:参数|arguments)[：:]\s*(\{.*?\})", re.DOTALL)


def extract_tool_invocations(text: str) -> Optional[List[Dict[str, Any]]]:
    """Extract tool invocations from response text"""
    if not text:
        return None
    
    # Limit scan size for performance
    scannable_text = text[:settings.SCAN_LIMIT]
    
    # Attempt 1: Extract from JSON code blocks
    json_blocks = TOOL_CALL_FENCE_PATTERN.findall(scannable_text)
    for json_block in json_blocks:
        try:
            parsed_data = json.loads(json_block)
            tool_calls = parsed_data.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                return tool_calls
        except (json.JSONDecodeError, AttributeError):
            continue
    
    # Attempt 2: Extract inline JSON objects
    inline_match = TOOL_CALL_INLINE_PATTERN.search(scannable_text)
    if inline_match:
        try:
            inline_json = inline_match.group(1)
            parsed_data = json.loads(inline_json)
            tool_calls = parsed_data.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                return tool_calls
        except (json.JSONDecodeError, AttributeError):
            pass
    
    # Attempt 3: Parse natural language function calls
    natural_lang_match = FUNCTION_CALL_PATTERN.search(scannable_text)
    if natural_lang_match:
        function_name = natural_lang_match.group(1).strip()
        arguments_str = natural_lang_match.group(2).strip()
        try:
            # Validate JSON format
            json.loads(arguments_str)
            return [{
                "id": f"invoke_{int(time.time() * 1000000)}",
                "type": "function",
                "function": {
                    "name": function_name,
                    "arguments": arguments_str
                }
            }]
        except json.JSONDecodeError:
            return None
    
    return None


def remove_tool_json_content(text: str) -> str:
    """Remove tool JSON content from response text"""
    def remove_tool_call_block(match: re.Match) -> str:
        json_content = match.group(1)
        try:
            parsed_data = json.loads(json_content)
            if "tool_calls" in parsed_data:
                return ""
        except (json.JSONDecodeError, AttributeError):
            pass
        return match.group(0)
    
    # Remove fenced tool JSON blocks
    cleaned_text = TOOL_CALL_FENCE_PATTERN.sub(remove_tool_call_block, text)
    # Remove inline tool JSON
    cleaned_text = TOOL_CALL_INLINE_PATTERN.sub("", cleaned_text)
    return cleaned_text.strip()