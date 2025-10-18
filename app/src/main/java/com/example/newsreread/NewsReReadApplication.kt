package com.example.newsreread

import android.app.Application
import com.example.newsreread.data.ApiClient
import com.example.newsreread.data.local.AppDatabase

class NewsReReadApplication : Application() {

    val database: AppDatabase by lazy { AppDatabase.getDatabase(this) }

    override fun onCreate() {
        super.onCreate()
        ApiClient.initialize(this)
    }
}
