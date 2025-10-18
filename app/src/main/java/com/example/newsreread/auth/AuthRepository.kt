package com.example.newsreread.auth

import android.content.Context
import com.example.newsreread.data.ApiClient
import com.example.newsreread.data.TokenPair
import com.example.newsreread.data.User

class AuthRepository(private val context: Context) {

    private val sharedPreferences = context.getSharedPreferences("auth", Context.MODE_PRIVATE)

    suspend fun register(username: String, email: String, password: String): User {
        val user = mapOf(
            "username" to username,
            "email" to email,
            "password" to password,
            "password2" to password
        )
        return ApiClient.apiService.register(user)
    }

    suspend fun login(username: String, password: String): TokenPair {
        val credentials = mapOf("username" to username, "password" to password)
        val tokenPair = ApiClient.apiService.login(credentials)
        saveTokens(tokenPair)
        return tokenPair
    }

    suspend fun refreshToken(): TokenPair? {
        val refreshToken = getRefreshToken()
        if (refreshToken != null) {
            try {
                val tokenPair = ApiClient.apiService.refreshToken(mapOf("refresh" to refreshToken))
                saveTokens(tokenPair)
                return tokenPair
            } catch (e: Exception) {
                // Refresh token failed, clear tokens
                logout()
            }
        }
        return null
    }

    fun getAccessToken(): String? {
        return sharedPreferences.getString("access_token", null)
    }

    fun getRefreshToken(): String? {
        return sharedPreferences.getString("refresh_token", null)
    }

    private fun saveTokens(tokenPair: TokenPair) {
        sharedPreferences.edit()
            .putString("access_token", tokenPair.access)
            .putString("refresh_token", tokenPair.refresh)
            .commit()
    }

    fun logout() {
        sharedPreferences.edit()
            .remove("access_token")
            .remove("refresh_token")
            .commit()
    }
}
