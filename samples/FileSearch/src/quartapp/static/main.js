// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE.md file in the project root for full license information.

import ChatUI from './ChatUI.js';
import ChatClient from './ChatClient.js';

function initChat() {
    const chatUI = new ChatUI();
    const chatClient = new ChatClient(chatUI);

    const form = document.getElementById("chat-form");

    form.addEventListener("submit", async function(e) {
        e.preventDefault();
        const thread_id = await chatClient.sendMessage("/chat");
        if (thread_id) {
            chatClient.listenToServer("/stream", thread_id);
        }
        chatClient.messageInput.value = "";
    });

    window.onbeforeunload = function() {
        chatClient.closeEventSource();
    };
}

document.addEventListener("DOMContentLoaded", initChat);
