import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/peer_chat_provider.dart';
import '../../chat/widgets/chat_bubble.dart';

class PeerChatScreen extends StatefulWidget {
  const PeerChatScreen({super.key});

  @override
  State<PeerChatScreen> createState() => _PeerChatScreenState();
}

class _PeerChatScreenState extends State<PeerChatScreen> {
  final _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<PeerChatProvider>().findPeerAndConnect();
    });
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
        title: Consumer<PeerChatProvider>(
          builder: (context, provider, child) {
            String title = 'Peer Chat';
            if (provider.state == PeerChatState.searching) {
              title = 'Finding a Partner...';
            } else if (provider.state == PeerChatState.connected) {
              title = 'Chatting with Partner';
            }
            return Text(title);
          },
        ),
        actions: [
          Consumer<PeerChatProvider>(
            builder: (context, provider, child) {
              return Padding(
                padding: const EdgeInsets.only(right: 16.0),
                child: Center(
                  child: Container(
                    width: 12,
                    height: 12,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: provider.state == PeerChatState.connected
                          ? Colors.green
                          : provider.state == PeerChatState.searching
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
      body: Consumer<PeerChatProvider>(
        builder: (context, provider, child) {
          if (provider.messages.isNotEmpty) {
            WidgetsBinding.instance.addPostFrameCallback(
              (_) => _scrollToBottom(),
            );
          }

          if (provider.state == PeerChatState.searching) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Stack(
                    alignment: Alignment.center,
                    children: [
                      SizedBox(
                        width: 100,
                        height: 100,
                        child: CircularProgressIndicator(
                          color: Theme.of(
                            context,
                          ).colorScheme.primary.withOpacity(0.5),
                          strokeWidth: 8,
                        ),
                      ),
                      const Icon(Icons.radar, size: 40, color: Colors.grey),
                    ],
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'Searching for someone to practice with...',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            );
          }

          return Column(
            children: [
              Expanded(
                child: provider.messages.isEmpty
                    ? const Center(
                        child: Text(
                          'Say Hello!',
                          style: TextStyle(color: Colors.grey, fontSize: 16),
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
              _buildInputArea(context, provider),
            ],
          );
        },
      ),
    );
  }

  Widget _buildInputArea(BuildContext context, PeerChatProvider provider) {
    if (provider.state != PeerChatState.connected) {
      return const SizedBox.shrink();
    }

    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      decoration: BoxDecoration(
        color: isDark ? Theme.of(context).colorScheme.surface : Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
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
                      ? Theme.of(context).colorScheme.background
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
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: provider.isRecording
                      ? Colors.red
                      : Theme.of(context).colorScheme.primary,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color:
                          (provider.isRecording
                                  ? Colors.red
                                  : Theme.of(context).colorScheme.primary)
                              .withOpacity(0.4),
                      blurRadius: 12,
                      spreadRadius: 2,
                    ),
                  ],
                ),
                child: Icon(
                  provider.isRecording ? Icons.stop : Icons.mic,
                  color: Colors.white,
                  size: 28,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
