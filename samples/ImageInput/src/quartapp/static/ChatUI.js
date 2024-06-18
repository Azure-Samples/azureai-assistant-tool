// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

class ChatUI {
    constructor() {
        this.targetContainer = document.getElementById("messages");
        this.userTemplate = document.querySelector('#message-template-user');
        this.assistantTemplate = document.querySelector('#message-template-assistant');
        if (!this.assistantTemplate) {
            console.error("Assistant template not found!");
        }
    }

    appendUserMessage(message, imageFiles = null) {
        const userTemplateClone = this.userTemplate.content.cloneNode(true);
        userTemplateClone.querySelector(".message-content").textContent = message;

        if (imageFiles) {
            userTemplateClone.querySelector(".message-content").innerHTML += "<br><br>";
            for (const imageFile of imageFiles){
                if (imageFile.type == "image/jpeg" || imageFile.type == "image/png" || imageFile.type == "image/gif" || imageFile.type == "image/webp") {
                    userTemplateClone.querySelector(".message-content").innerHTML += `<img src="${URL.createObjectURL(imageFile)}"${imageFile.name}" style="max-width: min(300px, 100%);"/>`;
                } else {
                    console.error("Unsupported file type")
                }
            }
        }
        
        this.targetContainer.appendChild(userTemplateClone);
        this.scrollToBottom();
    }

    appendAssistantMessage(messageDiv, accumulatedContent, isStreaming) {
        //console.log("Accumulated Content before conversion:", accumulatedContent);    
        const md = window.markdownit({
            html: true,
            linkify: true,
            typographer: true,
            breaks: true
        });
    
        try {
            // Convert the accumulated content to HTML using markdown-it
            let htmlContent = md.render(accumulatedContent);
            const messageTextDiv = messageDiv.querySelector(".message-text");
            if (!messageTextDiv) {
                throw new Error("Message content div not found in the template.");
            }
    
            // Set the innerHTML of the message text div to the HTML content
            messageTextDiv.innerHTML = htmlContent;
   
            // Use requestAnimationFrame to ensure the DOM has updated before scrolling
            // Only scroll if not streaming
            if (!isStreaming) {
                console.log("Accumulated content:", accumulatedContent);
                console.log("HTML set to messageTextDiv:", messageTextDiv.innerHTML);
                requestAnimationFrame(() => {
                    this.scrollToBottom();
                });
            }
        } catch (error) {
            console.error("Error in appendAssistantMessage:", error);
        }
    }

    clearAssistantMessage(messageDiv) {
        const messageTextDiv = messageDiv.querySelector(".message-text");
        if (messageTextDiv) {
            messageTextDiv.innerHTML = '';
        }
    }

    createAssistantMessageDiv() {
        const assistantTemplateClone = this.assistantTemplate.content.cloneNode(true);
        if (!assistantTemplateClone) {
            console.error("Failed to clone assistant template.");
            return null;
        }
    
        // Append the clone to the target container
        this.targetContainer.appendChild(assistantTemplateClone);
    
        // Since the content of assistantTemplateClone is now transferred to the DOM,
        // you should query the targetContainer for the elements you want to interact with.
        // Specifically, you look at the last added 'toast' which is where the new content lives.
        const newlyAddedToast = this.targetContainer.querySelector(".toast-container:last-child .toast:last-child");
       
        if (!newlyAddedToast) {
            console.error("Failed to find the newly added toast element.");
            return null;
        }
    
        // Now, find the .message-content within this newly added toast
        const messageDiv = newlyAddedToast.querySelector(".message-content");
    
        if (!messageDiv) {
            console.error("Message content div not found in the template.");
        }
    
        return messageDiv;
    }
    
    scrollToBottom() {
        const lastChild = this.targetContainer.lastElementChild;
        if (lastChild) {
            // Adjust the scroll to make sure the input box is visible
            lastChild.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
        
        // Ensure the input box remains visible
        const inputBox = document.querySelector('#chat-area');
        if (inputBox) {
            inputBox.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
    }
}

export default ChatUI;
