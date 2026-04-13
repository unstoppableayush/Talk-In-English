import 'package:flutter/material.dart';

class DashboardProvider extends ChangeNotifier {
  int _dailyStreak = 5;
  int _totalSpeakingMinutes = 120;
  List<String> _recentActivities = [];

  int get dailyStreak => _dailyStreak;
  int get totalSpeakingMinutes => _totalSpeakingMinutes;
  List<String> get recentActivities => _recentActivities;

  bool _isLoading = false;
  bool get isLoading => _isLoading;

  Future<void> fetchDashboardData() async {
    _isLoading = true;
    notifyListeners();

    // TODO: implement API call
    await Future.delayed(const Duration(seconds: 1));
    _recentActivities = [
      'Roleplay: Job Interview - 15m ago',
      'AI Chat Review - 2h ago',
      'Grammar Evaluation - Yesterday',
    ];

    _isLoading = false;
    notifyListeners();
  }
}
