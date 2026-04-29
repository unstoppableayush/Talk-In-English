import 'package:dio/dio.dart';

class ApiClient {
  // static const String baseUrl = 'http://localhost:8000/api/v1';
  static const String baseUrl = 'https://talk-in-english-84cd82ed9809.herokuapp.com/api/v1';
  // static const String wsUrl = 'ws://localhost:8000/ws';
  static const String wsUrl = 'talk-in-english-84cd82ed9809.herokuapp.com';
  static String? _token;

  static final Dio dio = Dio(
    BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 10),
      contentType: 'application/json',
      responseType: ResponseType.json,
    ),
  )..interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (_token != null) {
            options.headers['Authorization'] = 'Bearer $_token';
          }
          return handler.next(options);
        },
        onError: (DioException e, handler) {
          // You could handle global errors (like 401 token expiration) here
          return handler.next(e);
        },
      ),
    );

  static void setToken(String token) {
    _token = token;
  }

  static void clearToken() {
    _token = null;
  }

  static String get token => _token ?? '';
}
