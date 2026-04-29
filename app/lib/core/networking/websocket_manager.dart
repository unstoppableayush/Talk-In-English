import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../networking/api_client.dart';

/// WebSocket manager for handling different protocols (audio, roleplay, session)
class WebSocketManager {
  WebSocketChannel? _channel;
  bool _isConnected = false;

  bool get isConnected => _isConnected;

  /// Connect to audio endpoint (binary audio streaming)
  Future<void> connectToAudio({
    required String sessionId,
    required String language,
    required Function(Map<String, dynamic>) onMessage,
    required Function() onDisconnect,
  }) async {
    try {
      final url =
          '${ApiClient.wsUrl}/audio/$sessionId?token=${ApiClient.token}&language=$language';
      _channel = WebSocketChannel.connect(Uri.parse(url));
      _channel!.stream.listen(
        (message) {
          if (message is String) {
            try {
              final json = jsonDecode(message);
              onMessage(json);
            } catch (e) {
              print('Failed to decode message: $message');
            }
          }
        },
        onDone: () {
          _isConnected = false;
          onDisconnect();
        },
        onError: (err) {
          print('WebSocket error: $err');
          _isConnected = false;
          onDisconnect();
        },
      );
      _isConnected = true;
    } catch (e) {
      print('Failed to connect to audio WS: $e');
      _isConnected = false;
      rethrow;
    }
  }

  /// Connect to roleplay endpoint (JSON-based conversation)
  Future<void> connectToRoleplay({
    required String sessionId,
    required Function(Map<String, dynamic>) onMessage,
    required Function() onDisconnect,
  }) async {
    try {
      final url =
          '${ApiClient.wsUrl}/roleplay/$sessionId?token=${ApiClient.token}';
      _channel = WebSocketChannel.connect(Uri.parse(url));
      _channel!.stream.listen(
        (message) {
          if (message is String) {
            try {
              final json = jsonDecode(message);
              onMessage(json);
            } catch (e) {
              print('Failed to decode roleplay message: $message');
            }
          }
        },
        onDone: () {
          _isConnected = false;
          onDisconnect();
        },
        onError: (err) {
          print('WebSocket error: $err');
          _isConnected = false;
          onDisconnect();
        },
      );
      _isConnected = true;
    } catch (e) {
      print('Failed to connect to roleplay WS: $e');
      _isConnected = false;
      rethrow;
    }
  }

  /// Connect to session endpoint (JSON chat messages)
  Future<void> connectToSession({
    required String sessionId,
    String role = 'speaker',
    required Function(Map<String, dynamic>) onMessage,
    required Function() onDisconnect,
  }) async {
    try {
      final url =
          '${ApiClient.wsUrl}/session/$sessionId?token=${ApiClient.token}&role=$role';
      _channel = WebSocketChannel.connect(Uri.parse(url));
      _channel!.stream.listen(
        (message) {
          if (message is String) {
            try {
              final json = jsonDecode(message);
              onMessage(json);
            } catch (e) {
              print('Failed to decode session message: $message');
            }
          }
        },
        onDone: () {
          _isConnected = false;
          onDisconnect();
        },
        onError: (err) {
          print('WebSocket error: $err');
          _isConnected = false;
          onDisconnect();
        },
      );
      _isConnected = true;
    } catch (e) {
      print('Failed to connect to session WS: $e');
      _isConnected = false;
      rethrow;
    }
  }

  /// Send binary audio data
  void sendAudio(List<int> audioBytes) {
    if (!_isConnected || _channel == null) {
      print('WebSocket not connected');
      return;
    }
    try {
      _channel!.sink.add(audioBytes);
    } catch (e) {
      print('Failed to send audio: $e');
    }
  }

  /// Send JSON message
  void sendMessage(Map<String, dynamic> message) {
    if (!_isConnected || _channel == null) {
      print('WebSocket not connected');
      return;
    }
    try {
      _channel!.sink.add(jsonEncode(message));
    } catch (e) {
      print('Failed to send message: $e');
    }
  }

  /// Send text message (for simpler endpoints)
  void sendText(String text) {
    if (!_isConnected || _channel == null) {
      print('WebSocket not connected');
      return;
    }
    try {
      _channel!.sink.add(text);
    } catch (e) {
      print('Failed to send text: $e');
    }
  }

  /// Disconnect
  void disconnect() {
    _channel?.sink.close();
    _isConnected = false;
  }

  void dispose() {
    disconnect();
  }
}
