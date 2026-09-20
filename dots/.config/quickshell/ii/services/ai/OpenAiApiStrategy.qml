import QtQuick

ApiStrategy {
    property bool isReasoning: false
    property var toolCallAcc: ({})
    
    function buildEndpoint(model: AiModel): string {
        // console.log("[AI] Endpoint: " + model.endpoint);
        return model.endpoint;
    }

    function extractToolCall(rawContent) {
        const match = /\[\[ Function: (\w+)\(([\s\S]*?)\) \]\]/.exec(rawContent || "");
        if (!match) return null;
        let args = match[2].trim();
        try {
            JSON.parse(args);
        } catch (e) {
            args = "{}";
        }
        return { name: match[1], arguments: args };
    }

    function stripScaffolding(content) {
        return (content || "")
            .replace(/\s*<think>[\s\S]*?<\/think>\s*/g, " ")
            .replace(/```command\n[\s\S]*?```/g, "")
            .replace(/\[\[ Function:[\s\S]*?\]\]/g, "")
            .replace(/\[\[ Output of[^\]]*\]\]/g, "")
            .replace(/\*\*Command execution request\*\*[^\n]*\n?/g, "")
            .replace(/\n{3,}/g, "\n\n")
            .trim();
    }

    function buildRequestData(model: AiModel, messages, systemPrompt: string, temperature: real, tools: list<var>, filePath: string) {
        const history = [{ role: "system", content: systemPrompt }];
        let callSequence = 0;
        let lastToolCallId = null;

        for (let i = 0; i < messages.length; i++) {
            const message = messages[i];
            if (message.role === "assistant") {
                const toolCall = extractToolCall(message.rawContent);
                const content = stripScaffolding(message.rawContent);
                if (toolCall) {
                    const id = `call_${callSequence++}`;
                    lastToolCallId = id;
                    history.push({
                        role: "assistant",
                        content: content,
                        tool_calls: [{
                            id: id,
                            type: "function",
                            function: {
                                name: toolCall.name,
                                arguments: toolCall.arguments
                            }
                        }]
                    });
                } else {
                    history.push({ role: "assistant", content: content });
                }
            } else if (message.role === "user" && message.functionName && lastToolCallId) {
                const output = message.functionResponse?.length > 0
                    ? message.functionResponse
                    : stripScaffolding(message.rawContent);
                history.push({ role: "tool", tool_call_id: lastToolCallId, content: output });
                lastToolCallId = null;
            } else {
                history.push({ role: message.role, content: message.rawContent });
            }
        }

        let baseData = {
            "model": model.model,
            "messages": history,
            "stream": true,
            "tools": tools,
            "temperature": temperature,
        };
        return model.extraParams ? Object.assign({}, baseData, model.extraParams) : baseData;
    }

    function buildAuthorizationHeader(apiKeyEnvVarName: string): string {
        return `-H "Authorization: Bearer \$\{${apiKeyEnvVarName}\}"`;
    }

    function hasPendingToolCall() {
        return Object.keys(toolCallAcc).length > 0;
    }

    function emitToolCall(message) {
        const keys = Object.keys(toolCallAcc);
        if (keys.length === 0) return { finished: true };

        const toolCall = toolCallAcc[keys[0]];
        let args = {};
        try {
            args = toolCall.args?.length > 0 ? JSON.parse(toolCall.args) : {};
        } catch (e) {
            const warning = `\n\n[[ Tool call ${toolCall.name}: could not parse arguments: ${toolCall.args} ]]\n`;
            message.rawContent += warning;
            message.content += warning;
            toolCallAcc = ({});
            return { finished: true };
        }

        const content = `\n\n[[ Function: ${toolCall.name}(${JSON.stringify(args, null, 2)}) ]]\n`;
        message.rawContent += content;
        message.content += content;
        message.functionName = toolCall.name;
        toolCallAcc = ({});
        return {
            functionCall: { name: toolCall.name, args: args },
            finished: true
        };
    }

    function parseResponseLine(line, message) {
        // Remove 'data: ' prefix if present and trim whitespace
        let cleanData = line.trim();
        if (cleanData.startsWith("data:")) {
            cleanData = cleanData.slice(5).trim();
        }

        // console.log("[AI] OpenAI: Data:", cleanData);
        
        // Handle special cases
        if (!cleanData || cleanData.startsWith(":")) return {};
        if (cleanData === "[DONE]") {
            if (hasPendingToolCall()) return emitToolCall(message);
            return { finished: true };
        }
        
        // Real stuff
        try {
            const dataJson = JSON.parse(cleanData);

            // Error response handling
            if (dataJson.error) {
                const errorMsg = `**Error**: ${dataJson.error.message || JSON.stringify(dataJson.error)}`;
                message.rawContent += errorMsg;
                message.content += errorMsg;
                return { finished: true };
            }

            const choice = dataJson.choices?.[0];
            const delta = choice?.delta;
            const finishReason = choice?.finish_reason;

            if (delta?.tool_calls) {
                for (const fragment of delta.tool_calls) {
                    const index = fragment.index ?? 0;
                    if (!toolCallAcc[index]) toolCallAcc[index] = { name: "", args: "" };
                    if (fragment.function?.name) toolCallAcc[index].name = fragment.function.name;
                    if (fragment.function?.arguments) toolCallAcc[index].args += fragment.function.arguments;
                }
            }

            let newContent = "";

            const responseContent = delta?.content || dataJson.message?.content;
            const responseReasoning = delta?.reasoning || delta?.reasoning_content;

            if (responseContent && responseContent.length > 0) {
                if (isReasoning) {
                    isReasoning = false;
                    const endBlock = "\n\n</think>\n\n";
                    message.content += endBlock;
                    message.rawContent += endBlock;
                }
                newContent = responseContent;
            } else if (responseReasoning && responseReasoning.length > 0) {
                if (!isReasoning) {
                    isReasoning = true;
                    const startBlock = "\n\n<think>\n\n";
                    message.rawContent += startBlock;
                    message.content += startBlock;
                }
                newContent = responseReasoning;
            }

            message.content += newContent;
            message.rawContent += newContent;

            if (finishReason && hasPendingToolCall()) {
                return emitToolCall(message);
            }

            // Usage metadata
            if (dataJson.usage) {
                return {
                    tokenUsage: {
                        input: dataJson.usage.prompt_tokens ?? -1,
                        output: dataJson.usage.completion_tokens ?? -1,
                        total: dataJson.usage.total_tokens ?? -1
                    },
                    finished: !!finishReason
                };
            }

            if (dataJson.done || finishReason) {
                if (hasPendingToolCall()) return emitToolCall(message);
                return { finished: true };
            }
            
        } catch (e) {
            console.log("[AI] OpenAI: Could not parse line: ", e);
            message.rawContent += line;
            message.content += line;
        }
        
        return {};
    }
    
    function onRequestFinished(message) {
        if (hasPendingToolCall()) return emitToolCall(message);
        return {};
    }
    
    function reset() {
        isReasoning = false;
        toolCallAcc = ({});
    }

}
