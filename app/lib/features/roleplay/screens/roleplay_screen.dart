import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/roleplay_provider.dart';
import '../../chat/widgets/chat_bubble.dart';

class RoleplayScreen extends StatefulWidget {
  const RoleplayScreen({super.key});

  @override
  State<RoleplayScreen> createState() => _RoleplayScreenState();
}

class _RoleplayScreenState extends State<RoleplayScreen> {
  final _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<RoleplayProvider>().loadScenarios();
    });
  }

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
        title: const Text('Roleplay Practice'),
        actions: [
          Consumer<RoleplayProvider>(
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
                          : provider.isConnecting
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
      body: Consumer<RoleplayProvider>(
        builder: (context, provider, child) {
          // If session not started, show scenario selection
          if (provider.sessionId == null) {
            return _buildScenarioSelection(context, provider);
          }

          // Session in progress - show chat
          if (provider.messages.isNotEmpty) {
            WidgetsBinding.instance.addPostFrameCallback(
              (_) => _scrollToBottom(),
            );
          }

          return Column(
            children: [
              Expanded(
                child: provider.messages.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            if (provider.isConnecting)
                              const CircularProgressIndicator()
                            else
                              Text(
                                'Act out your scenario!',
                                style: TextStyle(
                                  color: Colors.grey.shade500,
                                  fontSize: 16,
                                ),
                              ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.only(bottom: 20, top: 10),
                        itemCount: provider.messages.length,
                        itemBuilder: (context, index) {
                          return ChatBubble(
                            message: provider.messages[index],
                          );
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

  Widget _buildScenarioSelection(
    BuildContext context,
    RoleplayProvider provider,
  ) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    if (provider.isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Select a Scenario',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 24),
          if (provider.scenarios.isEmpty)
            Center(
              child: Text(
                'No scenarios available',
                style: TextStyle(color: Colors.grey.shade500),
              ),
            )
          else
            Column(
              children: [
                ...provider.scenarios.map((scenario) {
                  return Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    child: Material(
                      child: InkWell(
                        onTap: () {
                          provider.selectScenario(scenario['id']);
                        },
                        child: Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: isDark
                                ? const Color(0xFF1E293B)
                                : Colors.grey.shade100,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: Theme.of(context).colorScheme.primary,
                              width: 2,
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                scenario['title'] ?? 'Untitled',
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              if (scenario['description'] != null) ...[
                                const SizedBox(height: 8),
                                Text(
                                  scenario['description'],
                                  style: TextStyle(
                                    color: Colors.grey.shade600,
                                    fontSize: 14,
                                  ),
                                ),
                              ],
                              const SizedBox(height: 12),
                              Row(
                                children: [
                                  Chip(
                                    label:
                                        Text(scenario['difficulty'] ?? 'N/A'),
                                    backgroundColor: Theme.of(context)
                                        .colorScheme
                                        .primary
                                        .withValues(alpha: 0.2),
                                  ),
                                  if (scenario['category'] != null) ...[
                                    const SizedBox(width: 8),
                                    Chip(
                                      label: Text(scenario['category']),
                                      backgroundColor:
                                          Colors.blue.withValues(alpha: 0.2),
                                    ),
                                  ],
                                ],
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  );
                }).toList(),
              ],
            ),
          const SizedBox(height: 24),
          Text(
            'Difficulty',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            children: ['beginner', 'intermediate', 'advanced']
                .map((level) {
                  final isSelected = provider.difficulty == level;
                  return FilterChip(
                    label: Text(level.toUpperCase()),
                    selected: isSelected,
                    onSelected: (_) {
                      provider.setDifficulty(level);
                    },
                    selectedColor: Theme.of(context)
                        .colorScheme
                        .primary
                        .withValues(alpha: 0.2),
                  );
                })
                .toList(),
          ),
          const SizedBox(height: 32),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: provider.scenarios.isEmpty
                  ? null
                  : () => provider.startRoleplay(),
              child: const Text('Start Roleplay'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputArea(BuildContext context, RoleplayProvider provider) {
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
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: provider.isRecording ? Colors.red : Theme.of(context).colorScheme.primary,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: (provider.isRecording
                              ? Colors.red
                              : Theme.of(context).colorScheme.primary)
                          .withValues(alpha: 0.4),
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
            const SizedBox(width: 12),
            GestureDetector(
              onTap: () => provider.endRoleplay(),
              child: Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.red.shade100,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  Icons.close,
                  color: Colors.red.shade600,
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
