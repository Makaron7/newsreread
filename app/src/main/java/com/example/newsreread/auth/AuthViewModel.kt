package com.example.newsreread.auth

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.newsreread.data.ApiClient
import com.example.newsreread.data.RegisterErrorResponse
import com.example.newsreread.data.User
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import retrofit2.HttpException

sealed class AuthState {
    object Loading : AuthState()
    object LoggedOut : AuthState()
    data class LoggedIn(val user: User) : AuthState()
    object LocalMode : AuthState()
    data class Error(val message: String) : AuthState()
}

class AuthViewModel(application: Application) : AndroidViewModel(application) {

    private val authRepository = AuthRepository(application.applicationContext)

    private val _authState = MutableStateFlow<AuthState>(AuthState.Loading)
    val authState: StateFlow<AuthState> = _authState

    init {
        checkLoginStatus()
    }

    private fun checkLoginStatus() {
        viewModelScope.launch {
            val token = authRepository.getAccessToken()
            if (token != null) {
                try {
                    val user = ApiClient.apiService.getUser()
                    _authState.value = AuthState.LoggedIn(user)
                } catch (e: Exception) {
                    authRepository.logout()
                    _authState.value = AuthState.LoggedOut
                }
            } else {
                _authState.value = AuthState.LoggedOut
            }
        }
    }

    fun login(username: String, password: String) {
        viewModelScope.launch {
            _authState.value = AuthState.Loading
            try {
                authRepository.login(username, password)
                checkLoginStatus()
            } catch (e: Exception) {
                _authState.value = AuthState.Error(e.message ?: "Login failed")
            }
        }
    }

    fun register(username: String, email: String, password: String) {
        viewModelScope.launch {
            _authState.value = AuthState.Loading
            try {
                authRepository.register(username, email, password)
                // Log in automatically after registration
                login(username, password)
            } catch (e: HttpException) {
                val errorBody = e.response()?.errorBody()?.string()
                if (errorBody != null) {
                    try {
                        val errorResponse = Json.decodeFromString<RegisterErrorResponse>(errorBody)
                        val errorMessage = buildString {
                            errorResponse.username?.let { append("Username: ${it.joinToString()}") }
                            errorResponse.password?.let { append("Password: ${it.joinToString()}") }
                            errorResponse.email?.let { append("Email: ${it.joinToString()}") }
                        }
                        _authState.value = AuthState.Error(errorMessage)
                    } catch (jsonException: Exception) {
                        _authState.value = AuthState.Error("An unknown error occurred during registration.")
                    }
                } else {
                    _authState.value = AuthState.Error("An unknown error occurred during registration.")
                }
            } catch (e: Exception) {
                _authState.value = AuthState.Error(e.message ?: "Registration failed")
            }
        }
    }

    fun logout() {
        authRepository.logout()
        _authState.value = AuthState.LoggedOut
    }

    fun useLocalMode() {
        _authState.value = AuthState.LocalMode
    }
}
