package com.example.newsreread.ui

import android.app.Application
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.example.newsreread.data.SettingsRepository

class SettingsViewModel(private val repository: SettingsRepository) : ViewModel() {

    val showUrl = repository.showUrl
    val showSummary = repository.showSummary
    val showMemo = repository.showMemo

    fun setShowUrl(show: Boolean) {
        repository.setShowUrl(show)
    }

    fun setShowSummary(show: Boolean) {
        repository.setShowSummary(show)
    }

    fun setShowMemo(show: Boolean) {
        repository.setShowMemo(show)
    }
}

class SettingsViewModelFactory(private val application: Application) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(SettingsViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return SettingsViewModel(SettingsRepository(application)) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
