import { defineStore } from 'pinia'
function _indexLayerRefs(groupedStack) {
    for (let i = 0; i < groupedStack.length; i++) {
        // first remove the duplicates from the references (same title and url)
        if (!groupedStack[i].references || !groupedStack[i].references.knowledge_items)
            continue
        groupedStack[i].references.knowledge_items = groupedStack[i].references.knowledge_items.filter((v, i, a) => a.findIndex(t => (t.url === v.url && t.title === v.title)) === i)
        // add the reference index to the layer index inside layerToReferences
        let refs = groupedStack[i].references.knowledge_items;
        for (let j = 0; j < groupedStack[i].layers.length; j++) {
            const layer = groupedStack[i].layers[j]
            if (layer.payload.references) {
                layer.referenceIndexes = layer.payload.references.knowledge_items.map(ref => refs.findIndex(r => r.url === ref.url && r.title === ref.title)).filter(i => i !== -1)
                // layer.referenceIndexes is a list of integer, no integer should repeat:
                layer.referenceIndexes = layer.referenceIndexes.filter((v, i, a) => a.findIndex(t => (t === v)) === i)
            }
        }
    }
}
export const useGlobalStore = defineStore('globalStore', {
    state: () => {
        return {
            fsmDef: undefined,
            chatfaqWS: {},
            chatfaqAPI: {},
            userId: undefined,
            title: "",
            subtitle: "",
            darkMode: false,
            menuOpened: false,
            maximized: true,
            historyOpened: true,
            conversations: [],
            messages: [],
            selectedConversations: [],
            selectedPlConversationId: undefined,
            // The value of this properties (scrollToBottom, feedbackSent) is irrelevant, what it
            // really matters is the fact that its value changed, which happens every time "New Conversation" button is
            // clicked, then other components will subscribe for any change and react to the fact that has been clicked
            scrollToBottom: 0,
            feedbackSent: 0,
            opened: false,
            deleting: false,
            downloading: false,
            disconnected: true,
            isPhone: false,
            displayGeneration: true,
            displaySources: true,
            sourcesFirst: false
        }
    },
    actions: {
        async gatherConversations() {
            let response = await fetch(this.chatfaqAPI + `/back/api/broker/conversations/from_sender/?sender=${this.userId}`);
            this.conversations = await response.json();
        },
        async renameConversationName(id, name) {
            await fetch(this.chatfaqAPI + `/back/api/broker/conversations/${id}/`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name })
            });
            this.conversations.find((conversation) => conversation.id === id).name = name;
        },
        async openConversation(_selectedPlConversationId) {
            const conversationId = this.conversations.find(conv => conv.platform_conversation_id.toString() === _selectedPlConversationId.toString()).id
            let response = await fetch(this.chatfaqAPI + `/back/api/broker/conversations/${conversationId}/`, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });
            response = await response.json();
            this.messages = response.mml_chain
            this.selectedPlConversationId = _selectedPlConversationId;
        },
        createNewConversation() {
            this.messages = [];
            this.selectedPlConversationId = Math.floor(Math.random() * 1000000000);
        },
        addMessage(message) {
            const index = this.messages.findIndex(m => m.id === message.id)
            if (index !== -1)
                this.messages[index] = message
            else
                this.messages.push(message)
        }
    },
    getters: {
        conversationsIds() {
            return this.conversations.reduce((acc, current) => acc.concat([current.id]), [])
        },
        waitingForResponse() {
            const msgs = this.messages
            return !msgs.length ||
            (msgs[msgs.length - 1].sender.type === 'human') ||
            (msgs[msgs.length - 1].sender.type === 'bot' &&
            !msgs[msgs.length - 1].last)
        },
        lastMsg() {
            const msgs = this.messages;
            if (!msgs.length)
                return undefined
            return msgs[msgs.length - 1]
        }
    }
})
