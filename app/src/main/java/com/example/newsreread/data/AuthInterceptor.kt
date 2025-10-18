package com.example.newsreread.data

import com.example.newsreread.auth.AuthRepository
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(private val authRepository: AuthRepository) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val accessToken = authRepository.getAccessToken()

        if (accessToken == null) {
            return chain.proceed(originalRequest)
        }

        val authenticatedRequest = originalRequest.newBuilder()
            .header("Authorization", "Bearer $accessToken")
            .build()

        var response = chain.proceed(authenticatedRequest)

        if (response.code == 401) {
            synchronized(this) {
                // Re-check the token, it might have been refreshed by another thread
                val newAccessToken = authRepository.getAccessToken()
                if (newAccessToken != accessToken) {
                    // Token was refreshed, retry with the new token
                    response.close()
                    val newAuthenticatedRequest = originalRequest.newBuilder()
                        .header("Authorization", "Bearer $newAccessToken")
                        .build()
                    return chain.proceed(newAuthenticatedRequest)
                }

                // Token not refreshed yet, so we'll try to refresh it
                val refreshedTokenPair = runBlocking { authRepository.refreshToken() }

                if (refreshedTokenPair != null) {
                    // Refresh succeeded, retry the request with the new access token
                    response.close()
                    val newAuthenticatedRequest = originalRequest.newBuilder()
                        .header("Authorization", "Bearer ${refreshedTokenPair.access}")
                        .build()
                    return chain.proceed(newAuthenticatedRequest)
                } else {
                    // Refresh failed, logout the user
                    runBlocking { authRepository.logout() }
                }
            }
        }

        return response
    }
}
