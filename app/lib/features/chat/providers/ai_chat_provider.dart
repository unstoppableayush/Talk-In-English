import 'package:flutter/material.dart';
import '../models/chat_message.dart';
import '../../../core/networking/websocket_manager.dart';
import '../../../core/services/room_service.dart';

class AiChatProvider extends ChangeNotifier {
  final WebSocketManager _sessionWsManager = WebSocketManager();
  final WebSocketManager _audioWsManager = WebSocketManager();
  final RoomService _roomService = RoomService();

  bool _isConnected = false;
  bool _isConnecting = false;
  bool _isRecording = false;
  String? _sessionId;
  bool _isStarting = false;

  final List<ChatMessage> _messages = [];

  bool get isConnected => _isConnected;
  bool get isConnecting => _isConnecting;
  bool get isRecording => _isRecording;
  bool get isStarting => _isStarting;
  String? get sessionId => _sessionId;
  List<ChatMessage> get messages => List.unmodifiable(_messages);

  /// Start a new AI chat session by creating a room and joining it
  Future<void> startSession() async {
    if (_isStarting || _sessionId != null) return;

    _isStarting = true;
    _isConnecting = true;
    notifyListeners();

    try {
      // Create room and get session_id
      final sessionId = await _roomService.createAndJoinAiRoom(
        name: 'AI Practice',
        topic: 'General conversation',
      );

      _sessionId = sessionId;
      debugPrint('Session created: $sessionId');

      // Connect to session WebSocket for chat messages
      await _sessionWsManager.connectToSession(
        sessionId: sessionId,
        role: 'speaker',
        onMessage: _handleIncomingMessage,
        onDisconnect: _handleDisconnect,
      );

      _isConnected = true;
    } catch (e) {
      debugPrint('Failed to start session: $e');
      _sessionId = null;
      _isConnected = false;
    } finally {
      _isStarting = false;
      _isConnecting = false;
      notifyListeners();
    }
  }

  void _handleIncomingMessage(Map<String, dynamic> json) {
    // Handle backend responses
    final event = json['event'];
    final data = json['data'];

    if (event == 'message.received' && data != null) {
      final text = data['content'] ?? '';
      if (text.isNotEmpty) {
        final isUser = (data['sender_type'] ?? '') == 'user';
        final createdAt = data['created_at'] as String?;
        _messages.add(
          ChatMessage(
            id: data['id'] ?? DateTime.now().millisecondsSinceEpoch.toString(),
            text: text,
            isUser: isUser,
            timestamp: createdAt != null
                ? DateTime.tryParse(createdAt) ?? DateTime.now()
                : DateTime.now(),
          ),
        );
        notifyListeners();
      }
    }
  }

  void _handleDisconnect() {
    _isConnected = false;
    notifyListeners();
  }

  /// Send binary audio data (16kHz, 16-bit PCM)
  void sendAudio(List<int> audioBytes) {
    if (!_isConnected) {
      debugPrint('Not connected to WebSocket');
      return;
    }
    _audioWsManager.sendAudio(audioBytes);
  }

  /// Send a text-based message (for testing without audio)
  void sendMessage(String text) {
    if (text.trim().isEmpty || !_isConnected) return;

    _sessionWsManager.sendMessage({
      'event': 'message.send',
      'data': {'content': text.trim()},
    });
  }

  void toggleRecording() {
    _isRecording = !_isRecording;
    if (!_isRecording) {
      // TODO: Implement actual audio recording
      // For now, simulate a message
      Future.delayed(const Duration(milliseconds: 500), () {
        debugPrint('Recording ended - would send audio');
      });
    }
    notifyListeners();
  }

  /// End the session
  Future<void> endSession() async {
    if (_sessionId == null) return;

    try {
      await _roomService.endSession(_sessionId!);
      _sessionId = null;
      _isConnected = false;
      _sessionWsManager.disconnect();
      _audioWsManager.disconnect();
      _messages.clear();
    } catch (e) {
      debugPrint('Failed to end session: $e');
    } finally {
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _sessionWsManager.dispose();
    _audioWsManager.dispose();
    super.dispose();
  }
}
