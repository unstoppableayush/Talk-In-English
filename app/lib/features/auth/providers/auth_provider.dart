import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../../../core/networking/api_client.dart';

class AuthProvider extends ChangeNotifier {
  bool _isAuthenticated = false;
  bool _isLoading = false;
  String? _token;

  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;
  String? get token => _token;

  Future<void> login(String email, String password) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await ApiClient.dio.post(
        '/auth/login',
        data: {
          'email': email,
          'password': password,
        }
      );

      final token = response.data['tokens']?['access_token'];
      if (token != null) {
        ApiClient.setToken(token);
        _token = token;
        _isAuthenticated = true;
        debugPrint('Login successful');
      } else {
        throw Exception('No token received');
      }
    } on DioException catch (e) {
      debugPrint('Login failed: ${e.response?.data ?? e.message}');
      _isAuthenticated = false;
      _token = null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> register(String name, String email, String password) async {
    _isLoading = true;
    notifyListeners();

    try {
      final response = await ApiClient.dio.post(
        '/auth/register',
        data: {'display_name': name, 'email': email, 'password': password},
      );

      final token = response.data['tokens']?['access_token'];
      if (token != null) {
        ApiClient.setToken(token);
        _token = token;
        _isAuthenticated = true;
        debugPrint('Registration successful');
      } else {
        throw Exception('No token received');
      }
    } on DioException catch (e) {
      debugPrint('Registration failed: ${e.response?.data ?? e.message}');
      _isAuthenticated = false;
      _token = null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void logout() {
    _isAuthenticated = false;
    _token = null;
    ApiClient.clearToken();
    debugPrint('Logged out');
    notifyListeners();
  }

  Future<void> loginWithGoogle() async {
    _isLoading = true;
    notifyListeners();

    try {
      await GoogleSignIn.instance.initialize();
      final GoogleSignInAccount account = await GoogleSignIn.instance.authenticate(
        scopeHint: ['email'],
      );
      final GoogleSignInAuthentication auth = account.authentication;
      final String? idToken = auth.idToken;
      if (idToken == null) {
        throw Exception('No ID token received from Google');
      }

      // Send the ID token to your backend for verification and login
      final response = await ApiClient.dio.post(
        '/auth/google',
        data: {
          'id_token': idToken,
        },
      );

      final token = response.data['tokens']?['access_token'];
      if (token != null) {
        ApiClient.setToken(token);
        _token = token;
        _isAuthenticated = true;
        debugPrint('Google login successful');
      } else {
        throw Exception('No token received from backend');
      }
    } on DioException catch (e) {
      debugPrint('Google Login failed: \\${e.response?.data ?? e.message}');
      _isAuthenticated = false;
      _token = null;
      rethrow;
    } catch (e) {
      debugPrint('Google Login failed: $e');
      _isAuthenticated = false;
      _token = null;
      rethrow;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
