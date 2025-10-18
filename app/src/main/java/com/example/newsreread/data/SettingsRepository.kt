package com.example.newsreread.data

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

class SettingsRepository(context: Context) {
    private val sharedPreferences = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    private val _showUrl = MutableStateFlow(sharedPreferences.getBoolean("show_url", true))
    val showUrl: StateFlow<Boolean> = _showUrl

    private val _showSummary = MutableStateFlow(sharedPreferences.getBoolean("show_summary", true))
    val showSummary: StateFlow<Boolean> = _showSummary

    private val _showMemo = MutableStateFlow(sharedPreferences.getBoolean("show_memo", true))
    val showMemo: StateFlow<Boolean> = _showMemo

    fun setShowUrl(show: Boolean) {
        sharedPreferences.edit().putBoolean("show_url", show).apply()
        _showUrl.value = show
    }

    fun setShowSummary(show: Boolean) {
        sharedPreferences.edit().putBoolean("show_summary", show).apply()
        _showSummary.value = show
    }

    fun setShowMemo(show: Boolean) {
        sharedPreferences.edit().putBoolean("show_memo", show).apply()
        _showMemo.value = show
    }
}
