import 'package:flutter/material.dart';
import '../../chat/models/chat_message.dart';
import '../../../core/networking/websocket_manager.dart';
import '../../../core/services/roleplay_service.dart';
import 'dart:async';

class RoleplayProvider extends ChangeNotifier {
  final WebSocketManager _wsManager = WebSocketManager();
  final RoleplayService _roleplayService = RoleplayService();

  bool _isConnected = false;
  bool _isConnecting = false;
  bool _isRecording = false;
  bool _isLoading = false;
  String? _sessionId;

  final List<ChatMessage> _messages = [];
  final List<Map<String, dynamic>> _scenarios = [];
  String? _selectedScenarioId;
  String _difficulty = 'intermediate';

  bool get isConnected => _isConnected;
  bool get isConnecting => _isConnecting;
  bool get isRecording => _isRecording;
  bool get isLoading => _isLoading;
  String? get sessionId => _sessionId;
  List<ChatMessage> get messages => List.unmodifiable(_messages);
  List<Map<String, dynamic>> get scenarios => List.unmodifiable(_scenarios);
  String get difficulty => _difficulty;

  /// Load available roleplay scenarios
  Future<void> loadScenarios() async {
    _isLoading = true;
    notifyListeners();

    try {
      final scenarios = await _roleplayService.fetchScenarios();
      _scenarios.clear();
      _scenarios.addAll(scenarios);
    } catch (e) {
      debugPrint('Failed to load scenarios: $e');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Select a scenario
  void selectScenario(String scenarioId) {
    _selectedScenarioId = scenarioId;
    notifyListeners();
  }

  /// Set difficulty level
  void setDifficulty(String difficulty) {
    _difficulty = difficulty;
    notifyListeners();
  }

  /// Start a roleplay session
  Future<void> startRoleplay() async {
    if (_isConnecting || _sessionId != null) return;
    if (_selectedScenarioId == null) {
      debugPrint('No scenario selected');
      return;
    }

    _isConnecting = true;
    _messages.clear();
    notifyListeners();

    try {
      // Start roleplay session via REST
      final sessionData = await _roleplayService.startSession(
        scenarioId: _selectedScenarioId,
        difficulty: _difficulty,
        language: 'en',
      );

      _sessionId = sessionData['id'] ?? sessionData['session_id'];
      if (_sessionId == null) {
        throw Exception('No session ID returned');
      }

      debugPrint('Roleplay session created: $_sessionId');

      // Add opening message if provided
      if (sessionData['opening_message'] != null) {
        final openingMsg = sessionData['opening_message'];
        _messages.add(ChatMessage(
          id: openingMsg['id'] ?? DateTime.now().millisecondsSinceEpoch.toString(),
          text: openingMsg['content'] ?? '',
          isUser: false,
          timestamp: DateTime.now(),
        ));
      }

      // Connect to roleplay WebSocket
      await _wsManager.connectToRoleplay(
        sessionId: _sessionId!,
        onMessage: _handleIncomingMessage,
        onDisconnect: _handleDisconnect,
      );

      _isConnected = true;
    } catch (e) {
      debugPrint('Failed to start roleplay: $e');
      _sessionId = null;
      _isConnected = false;
    } finally {
      _isConnecting = false;
      notifyListeners();
    }
  }

  void _handleIncomingMessage(Map<String, dynamic> json) {
    // Handle roleplay-specific messages
    final event = json['event'];
    final data = json['data'];

    if (event == 'roleplay.connected') {
      debugPrint('Connected to roleplay');
    } else if (event == 'roleplay.ai_reply' && data != null) {
      final content = data['content'] ?? '';
      if (content.isNotEmpty) {
        _messages.add(ChatMessage(
          id: data['id'] ?? DateTime.now().millisecondsSinceEpoch.toString(),
          text: content,
          isUser: false,
          timestamp: DateTime.now(),
        ));
        notifyListeners();
      }
    } else if (event == 'roleplay.ended') {
      debugPrint('Roleplay session ended');
      _handleDisconnect();
    }
  }

  void _handleDisconnect() {
    _isConnected = false;
    notifyListeners();
  }

  /// Send a message during roleplay
  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty || _sessionId == null) return;

    // Add user message to local list
    final message = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      text: text,
      isUser: true,
      timestamp: DateTime.now(),
    );
    _messages.add(message);
    notifyListeners();

    try {
      // Send via WebSocket using JSON protocol
      _wsManager.sendMessage({
        'event': 'roleplay.message',
        'data': {'content': text},
      });
    } catch (e) {
      debugPrint('Failed to send message: $e');
    }
  }

  void toggleRecording() {
    _isRecording = !_isRecording;
    if (!_isRecording) {
      // TODO: Implement actual audio recording
      debugPrint('Recording ended - would send audio');
    }
    notifyListeners();
  }

  /// End the roleplay session
  Future<void> endRoleplay() async {
    if (_sessionId == null) return;

    try {
      await _roleplayService.endSession(_sessionId!);
      _sessionId = null;
      _isConnected = false;
    } catch (e) {
      debugPrint('Failed to end roleplay: $e');
    } finally {
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _wsManager.dispose();
    super.dispose();
  }
}
