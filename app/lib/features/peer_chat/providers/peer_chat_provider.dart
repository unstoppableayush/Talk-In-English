import 'package:flutter/material.dart';
import '../../chat/models/chat_message.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'dart:async';

enum PeerChatState { searching, connected, disconnected }

class PeerChatProvider extends ChangeNotifier {
  WebSocketChannel? _channel;
  PeerChatState _state = PeerChatState.disconnected;
  bool _isRecording = false;

  final List<ChatMessage> _messages = [];

  PeerChatState get state => _state;
  bool get isRecording => _isRecording;
  List<ChatMessage> get messages => List.unmodifiable(_messages);

  Future<void> findPeerAndConnect() async {
    if (_state != PeerChatState.disconnected) return;

    _state = PeerChatState.searching;
    notifyListeners();

    try {
      // Simulate finding a peer
      await Future.delayed(const Duration(seconds: 3));

      // Simulate WS Connection
      _channel = WebSocketChannel.connect(
        Uri.parse('wss://echo.websocket.events'),
      );

      _state = PeerChatState.connected;
      notifyListeners();

      _channel?.stream.listen(
        (message) {
          _handleIncomingMessage(message.toString());
        },
        onDone: () {
          _handleDisconnect();
        },
        onError: (error) {
          _handleDisconnect();
        },
      );
    } catch (e) {
      _state = PeerChatState.disconnected;
      notifyListeners();
    }
  }

  void _handleIncomingMessage(String text) {
    if (text.isEmpty) return;
    _messages.add(
      ChatMessage(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        text: text,
        isUser: false,
        timestamp: DateTime.now(),
      ),
    );
    notifyListeners();
  }

  void _handleDisconnect() {
    _state = PeerChatState.disconnected;
    _channel = null;
    notifyListeners();
  }

  void disconnect() {
    _channel?.sink.close();
    _handleDisconnect();
  }

  void sendMessage(String text) {
    if (text.trim().isEmpty || _state != PeerChatState.connected) return;

    final message = ChatMessage(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      text: text,
      isUser: true,
      timestamp: DateTime.now(),
    );

    _messages.add(message);
    notifyListeners();

    _channel?.sink.add(text);
  }

  void toggleRecording() {
    _isRecording = !_isRecording;
    if (!_isRecording) {
      Future.delayed(const Duration(milliseconds: 500), () {
        sendMessage("This is a simulated voice message to my peer.");
      });
    }
    notifyListeners();
  }

  @override
  void dispose() {
    disconnect();
    super.dispose();
  }
}
