import 'package:dio/dio.dart';
import '../networking/api_client.dart';

class RoleplayService {
  static final RoleplayService _instance = RoleplayService._internal();

  factory RoleplayService() {
    return _instance;
  }

  RoleplayService._internal();

  /// Fetch available roleplay scenarios
  Future<List<Map<String, dynamic>>> fetchScenarios({
    String? category,
    String? difficulty,
    String language = 'en',
  }) async {
    try {
      final queryParams = {
        'language': language,
        if (category != null) 'category': category,
        if (difficulty != null) 'difficulty': difficulty,
      };

      final response = await ApiClient.dio.get(
        '/roleplay/scenarios',
        queryParameters: queryParams,
      );

      if (response.data is List) {
        return List<Map<String, dynamic>>.from(response.data);
      }
      return [];
    } on DioException catch (e) {
      throw Exception(
        'Failed to fetch scenarios: ${e.response?.data ?? e.message}',
      );
    }
  }

  /// Start a roleplay session
  Future<Map<String, dynamic>> startSession({
    String? scenarioId,
    String? customTopic,
    String difficulty = 'intermediate',
    String language = 'en',
  }) async {
    try {
      if (scenarioId == null && (customTopic == null || customTopic.isEmpty)) {
        throw Exception('Provide either scenarioId or customTopic');
      }

      final data = {
        'difficulty': difficulty,
        'language': language,
        if (scenarioId != null) 'scenario_id': scenarioId,
        if (customTopic != null) 'custom_topic': customTopic,
      };

      final response = await ApiClient.dio.post(
        '/roleplay/start-session',
        data: data,
      );

      return response.data;
    } on DioException catch (e) {
      throw Exception(
        'Failed to start roleplay session: ${e.response?.data ?? e.message}',
      );
    }
  }

  /// End a roleplay session
  Future<Map<String, dynamic>> endSession(String sessionId) async {
    try {
      final response = await ApiClient.dio.post(
        '/roleplay/sessions/$sessionId/end',
      );
      return response.data;
    } on DioException catch (e) {
      throw Exception(
        'Failed to end roleplay session: ${e.response?.data ?? e.message}',
      );
    }
  }

  /// Send a roleplay message
  Future<Map<String, dynamic>> sendMessage(
    String sessionId,
    String content,
  ) async {
    try {
      final response = await ApiClient.dio.post(
        '/roleplay/send-message',
        data: {
          'session_id': sessionId,
          'content': content,
        },
      );
      return response.data;
    } on DioException catch (e) {
      throw Exception(
        'Failed to send roleplay message: ${e.response?.data ?? e.message}',
      );
    }
  }

  /// Get roleplay session details
  Future<Map<String, dynamic>> getSession(String sessionId) async {
    try {
      final response = await ApiClient.dio.get(
        '/roleplay/sessions/$sessionId',
      );
      return response.data;
    } on DioException catch (e) {
      throw Exception(
        'Failed to fetch roleplay session: ${e.response?.data ?? e.message}',
      );
    }
  }

  /// Get roleplay evaluation report
  Future<Map<String, dynamic>> getReport(String sessionId) async {
    try {
      final response = await ApiClient.dio.get(
        '/roleplay/report/$sessionId',
      );
      return response.data;
    } on DioException catch (e) {
      throw Exception(
        'Failed to fetch roleplay report: ${e.response?.data ?? e.message}',
      );
    }
  }
}
