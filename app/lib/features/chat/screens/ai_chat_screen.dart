import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/ai_chat_provider.dart';
import '../widgets/chat_bubble.dart';

class AiChatScreen extends StatefulWidget {
  const AiChatScreen({super.key});

  @override
  State<AiChatScreen> createState() => _AiChatScreenState();
}

class _AiChatScreenState extends State<AiChatScreen> {
  final _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Coach'),
        actions: [
          Consumer<AiChatProvider>(
            builder: (context, provider, child) {
              return Padding(
                padding: const EdgeInsets.only(right: 16.0),
                child: Center(
                  child: Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: provider.isConnected
                          ? Colors.green
                          : provider.isConnecting || provider.isStarting
                          ? Colors.orange
                          : Colors.red,
                    ),
                  ),
                ),
              );
            },
          ),
        ],
      ),
      body: Consumer<AiChatProvider>(
        builder: (context, provider, child) {
          // Start session on first load
          if (provider.sessionId == null && !provider.isStarting) {
            WidgetsBinding.instance.addPostFrameCallback((_) {
              provider.startSession();
            });
          }

          if (provider.messages.isNotEmpty) {
            WidgetsBinding.instance.addPostFrameCallback(
              (_) => _scrollToBottom(),
            );
          }

          return Column(
            children: [
              Expanded(
                child: provider.sessionId == null
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            if (provider.isStarting)
                              const CircularProgressIndicator()
                            else
                              ElevatedButton(
                                onPressed: () => provider.startSession(),
                                child: const Text('Start Conversation'),
                              ),
                          ],
                        ),
                      )
                    : provider.messages.isEmpty
                    ? Center(
                        child: Text(
                          'Say something to start!',
                          style: TextStyle(
                            color: Colors.grey.shade500,
                            fontSize: 16,
                          ),
                        ),
                      )
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.only(bottom: 20, top: 20),
                        itemCount: provider.messages.length,
                        itemBuilder: (context, index) {
                          return ChatBubble(message: provider.messages[index]);
                        },
                      ),
              ),
              if (provider.sessionId != null)
                _buildInputArea(context, provider),
            ],
          );
        },
      ),
    );
  }

  Widget _buildInputArea(BuildContext context, AiChatProvider provider) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      decoration: BoxDecoration(
        color: isDark ? Theme.of(context).colorScheme.surface : Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            offset: const Offset(0, -4),
            blurRadius: 10,
          ),
        ],
      ),
      child: SafeArea(
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: _messageController,
                decoration: InputDecoration(
                  hintText: 'Type your message...',
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 12,
                  ),
                  filled: true,
                  fillColor: isDark
                      ? Theme.of(context).colorScheme.surface
                      : Colors.grey.shade100,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(30),
                    borderSide: BorderSide.none,
                  ),
                ),
                onSubmitted: (text) {
                  provider.sendMessage(text);
                  _messageController.clear();
                },
              ),
            ),
            const SizedBox(width: 12),
            GestureDetector(
              onTap: provider.toggleRecording,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: provider.isRecording
                      ? Colors.red.shade600
                      : Theme.of(context).colorScheme.primary,
                  boxShadow: [
                    if (provider.isRecording)
                      BoxShadow(
                        color: Colors.red.withValues(alpha: 0.5),
                        blurRadius: 10,
                        spreadRadius: 2,
                      )
                  ],
                ),
                child: Icon(
                  provider.isRecording ? Icons.stop : Icons.mic,
                  color: Colors.white,
                ),
              ),
            ),
            const SizedBox(width: 12),
            GestureDetector(
              onTap: () => provider.endSession(),
              child: Container(
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.red.shade100,
                ),
                child: Icon(
                  Icons.close,
                  color: Colors.red.shade600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
