import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../../../core/networking/api_client.dart';

class AuthProvider extends ChangeNotifier {
  bool _isAuthenticated = false;
  bool _isLoading = false;
  String? _token;
  String? _errorMessage;

  bool get isAuthenticated => _isAuthenticated;
  bool get isLoading => _isLoading;
  String? get token => _token;
  String? get errorMessage => _errorMessage;

  Future<void> login(String email, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await ApiClient.dio.post('/auth/login', data: {
        'email': email,
        'password': password,
      });

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
      _errorMessage = _formatDioError(e, fallback: 'Login failed');
      debugPrint('Login failed: $_errorMessage');
      _isAuthenticated = false;
      _token = null;
    } catch (e) {
      _errorMessage = 'Login failed. Please try again.';
      debugPrint('Login failed: $e');
      _isAuthenticated = false;
      _token = null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> register(String name, String email, String password) async {
    _isLoading = true;
    _errorMessage = null;
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
      _errorMessage = _formatDioError(e, fallback: 'Registration failed');
      debugPrint('Registration failed: $_errorMessage');
      _isAuthenticated = false;
      _token = null;
    } catch (e) {
      _errorMessage = 'Registration failed. Please try again.';
      debugPrint('Registration failed: $e');
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
    _errorMessage = null;
    notifyListeners();

    try {
      await GoogleSignIn.instance.initialize();
      final GoogleSignInAccount account =
          await GoogleSignIn.instance.authenticate(
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
      _errorMessage = _formatDioError(e, fallback: 'Google login failed');
      debugPrint('Google Login failed: $_errorMessage');
      _isAuthenticated = false;
      _token = null;
    } catch (e) {
      _errorMessage = 'Google login failed. Please try again.';
      debugPrint('Google Login failed: $e');
      _isAuthenticated = false;
      _token = null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  String _formatDioError(DioException e, {required String fallback}) {
    final data = e.response?.data;
    if (data is Map && data['detail'] != null) {
      return data['detail'].toString();
    }
    if (data is String && data.isNotEmpty) {
      return data;
    }
    return e.message ?? fallback;
  }
}
