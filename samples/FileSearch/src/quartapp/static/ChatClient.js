// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

class ChatClient {
    constructor(ui) {
        this.ui = ui;
        this.messageInput = document.getElementById("message");
        this.eventSource = null;
    }

    async sendMessage(url) {
        const message = this.messageInput.value.trim();
        if (!message) return false;

        this.ui.appendUserMessage(message);

        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message })
        });

        const data = await response.json();
        return data.thread_id;
    }

    listenToServer(url, threadID) {
        if (!this.eventSource || this.eventSource.readyState === EventSource.CLOSED) {
            this.eventSource = new EventSource(`${url}/${threadID}`);
            this.handleMessages();
        }
    }

    handleMessages() {
        let messageDiv = null;
        let accumulatedContent = '';
        let isStreaming = true;

        this.eventSource.onmessage = event => {
            const data = JSON.parse(event.data);

            if (data.type === "stream_end") {
                this.eventSource.close();
                messageDiv = null;
                accumulatedContent = '';
            } else {
                if (!messageDiv) {
                    messageDiv = this.ui.createAssistantMessageDiv();
                    if (!messageDiv) {
                        console.error("Failed to create message div.");
                    }
                }

                // Check if it's a completed message
                if (data.type === "completed_message") {
                    //console.log("Received completed message:", data.content);
                    // Replace the accumulated content with the completed message
                    this.ui.clearAssistantMessage(messageDiv);
                    accumulatedContent = data.content;
                    isStreaming = false;
                } else {
                    //console.log("Received partial message:", data.content);
                    // Append the partial message to the accumulated content
                    accumulatedContent += data.content;
                }

                this.ui.appendAssistantMessage(messageDiv, accumulatedContent, isStreaming);
            }
        };

        this.eventSource.onerror = error => {
            console.error("EventSource failed:", error);
            this.eventSource.close();
        };
    }

    closeEventSource() {
        if (this.eventSource) this.eventSource.close();
    }
}

export default ChatClient;
