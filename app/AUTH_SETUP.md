# Flutter App - Authentication Setup Guide

## Issue: "Not Authenticated" Error

When trying to use the Flutter app, you may see "Not authenticated" errors when trying to create a session. This is because:

1. **Google Login is currently mocked** - It attempts to use test credentials (`google@test.com / testpassword123`)
2. **That test account may not exist** on your backend
3. **You need to authenticate first** before using any features

## Solution: Create a Test Account

### Option 1: Use the Registration Screen (Recommended)

1. Launch the Flutter app
2. Go to the **Registration** tab
3. Create a new account with:
   - **Name**: Any name (e.g., "Test User")
   - **Email**: Any email (e.g., `test@example.com`)
   - **Password**: Any password (e.g., `password123`)
4. Click **Register**
5. You'll be automatically logged in with a valid token
6. Now you can use all features (AI Chat, Roleplay, etc.)

### Option 2: Create Test User on Backend (For Google Login Testing)

If you want the Google login to work with test credentials, create this user on the backend:

```
Email: google@test.com
Password: testpassword123
Display Name: Google Test User
```

#### Using curl:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "google@test.com",
    "password": "testpassword123",
    "display_name": "Google Test User"
  }'
```

#### Using Python:
```python
import requests

response = requests.post(
    'http://localhost:8000/api/v1/auth/register',
    json={
        'email': 'google@test.com',
        'password': 'testpassword123',
        'display_name': 'Google Test User'
    }
)
print(response.json())
```

### Option 3: Use Docker/Database Admin

If you have direct database access, create a user in the `auth.users` table:
- Email: `google@test.com`
- Password: (hashed, use backend's password hashing)
- Display Name: `Google Test User`

## How Authentication Works

1. **Login/Register** → Flutter app calls `/auth/login` or `/auth/register`
2. **Backend validates** credentials and returns `{tokens: {access_token: "..."}}`
3. **Flutter stores** the token in `ApiClient._token`
4. **Dio interceptor** automatically adds `Authorization: Bearer <token>` to all requests
5. **Backend validates** the token on each request

## Current Google Login Implementation

The Google login button currently:
- Attempts to login with test credentials (`google@test.com / testpassword123`)
- Does NOT use real Google OAuth yet (requires setup)
- Will fail if that test user doesn't exist

### Future: Real Google OAuth

To implement real Google Sign-In, you need to:

1. Install the `google_sign_in` package
2. Configure Google OAuth credentials
3. Update `auth_provider.dart`:
   ```dart
   final GoogleSignIn _googleSignIn = GoogleSignIn();
   final GoogleSignInAccount? googleUser = await _googleSignIn.signIn();
   final GoogleSignInAuthentication googleAuth = await googleUser!.authentication;
   final response = await ApiClient.dio.post('/auth/google', 
     data: {'id_token': googleAuth.idToken}
   );
   ```
4. Implement `/auth/google` endpoint on backend

## Debugging: Check Your Token

After logging in, you can check if token was set by:
1. Looking at console logs for "Login successful"
2. The app should successfully create a session and connect to WebSocket
3. If you still see "Not authenticated", the token wasn't set

## Test Flow

1. **Register** → Get token
2. **Press "AI Chat" button** → Starts session (requires token)
3. **See messages** → WebSocket connected + authenticated
4. **Send message** → Should work without auth errors

If you see "Not authenticated" at the start session step, the token is not being set. Check:
- Console logs for login errors
- Backend is running and accessible at `http://localhost:8000`
- Network tab to see if requests include `Authorization` header
