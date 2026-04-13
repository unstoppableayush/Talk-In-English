import 'package:dio/dio.dart';
import '../networking/api_client.dart';

class RoomService {
  static final RoomService _instance = RoomService._internal();

  factory RoomService() {
    return _instance;
  }

  RoomService._internal();

  /// Create a room and join it to get a session_id
  Future<String> createAndJoinAiRoom({
    required String name,
    required String topic,
  }) async {
    try {
      // Step 1: Create room
      final roomResponse = await ApiClient.dio.post(
        '/rooms',
        data: {
          'name': name,
          'room_type': 'one_on_one',
          'topic': topic,
        },
      );

      final roomId = roomResponse.data['id'];
      if (roomId == null) {
        throw Exception('Failed to create room: no room ID returned');
      }

      // Step 2: Join room and get session_id
      final sessionResponse = await ApiClient.dio.post(
        '/rooms/$roomId/join',
        data: {'role': 'speaker'},
      );

      final sessionId = sessionResponse.data['session_id'];
      if (sessionId == null) {
        throw Exception('Failed to join room: no session_id returned');
      }

      return sessionId;
    } on DioException catch (e) {
      throw Exception(
        'Room creation failed: ${e.response?.data ?? e.message}',
      );
    }
  }

  /// End a session
  Future<void> endSession(String sessionId) async {
    try {
      await ApiClient.dio.post('/sessions/$sessionId/end');
    } on DioException catch (e) {
      throw Exception(
        'Failed to end session: ${e.response?.data ?? e.message}',
      );
    }
  }

  /// Fetch session details
  Future<Map<String, dynamic>> getSession(String sessionId) async {
    try {
      final response = await ApiClient.dio.get('/sessions/$sessionId');
      return response.data;
    } on DioException catch (e) {
      throw Exception(
        'Failed to fetch session: ${e.response?.data ?? e.message}',
      );
    }
  }

  /// Send message via session WebSocket
  Future<void> sendSessionMessage(String sessionId, String content) async {
    try {
      await ApiClient.dio.post(
        '/sessions/$sessionId/messages',
        data: {'content': content},
      );
    } on DioException catch (e) {
      throw Exception(
        'Failed to send message: ${e.response?.data ?? e.message}',
      );
    }
  }
}
