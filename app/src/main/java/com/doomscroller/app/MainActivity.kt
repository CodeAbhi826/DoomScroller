package com.doomscroller.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.doomscroller.app.data.AppPreferences
import com.doomscroller.app.databinding.ActivityMainBinding
import com.doomscroller.app.service.AutoScrollAccessibilityService

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var preferences: AppPreferences

    private val statusListener: (Boolean) -> Unit = { isRunning ->
        runOnUiThread {
            updateServiceStatusUI(isRunning)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        preferences = AppPreferences(this)

        setupUI()
        setupListeners()
    }

    override fun onResume() {
        super.onResume()
        AutoScrollAccessibilityService.registerStatusListener(statusListener)
        // Also verify whether accessibility is recognized by system
        val isA11yEnabled = isAccessibilityServiceEnabled()
        updateServiceStatusUI(isA11yEnabled || AutoScrollAccessibilityService.isServiceRunning)
    }

    override fun onPause() {
        super.onPause()
        AutoScrollAccessibilityService.unregisterStatusListener(statusListener)
    }

    private fun setupUI() {
        // Load preferences into switches
        binding.switchAutoScroll.isChecked = preferences.isAutoScrollEnabled
        binding.switchPauseComments.isChecked = preferences.pauseOnComments

        binding.switchAutoScroll.setOnCheckedChangeListener { _, isChecked ->
            preferences.isAutoScrollEnabled = isChecked
            val msg = if (isChecked) "Auto-scroll activated" else "Auto-scroll paused"
            Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
        }

        binding.switchPauseComments.setOnCheckedChangeListener { _, isChecked ->
            preferences.pauseOnComments = isChecked
        }
    }

    private fun setupListeners() {
        // Accessibility Settings Button
        binding.btnEnableService.setOnClickListener {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            startActivity(intent)
            Toast.makeText(
                this,
                "Find 'DoomScroller Auto-Scroll Service' in Installed Apps and toggle ON",
                Toast.LENGTH_LONG
            ).show()
        }

        // Battery Optimization Exemption
        binding.btnBatteryOpt.setOnClickListener {
            requestBatteryOptimizationExemption()
        }

        // Direct YouTube Shorts Launch Button
        binding.btnOpenYouTube.setOnClickListener {
            launchYouTubeShorts()
        }
    }

    private fun updateServiceStatusUI(isActive: Boolean) {
        if (isActive) {
            binding.cardStatus.strokeColor = ContextCompat.getColor(this, R.color.card_stroke)
            binding.layoutStatusBadge.background = ContextCompat.getDrawable(this, R.drawable.bg_status_pill)
            binding.ivStatusDot.setColorFilter(ContextCompat.getColor(this, R.color.status_green))
            binding.tvStatusBadge.text = "ACTIVE & MONITORING"
            binding.tvStatusBadge.setTextColor(ContextCompat.getColor(this, R.color.status_green))
            binding.tvStatusTitle.text = getString(R.string.status_active)
            binding.tvStatusDesc.text = getString(R.string.service_enabled_desc)
            binding.btnEnableService.visibility = View.GONE
        } else {
            binding.cardStatus.strokeColor = ContextCompat.getColor(this, R.color.status_amber)
            binding.layoutStatusBadge.background = ContextCompat.getDrawable(this, R.drawable.bg_status_pill_amber)
            binding.ivStatusDot.setColorFilter(ContextCompat.getColor(this, R.color.status_amber))
            binding.tvStatusBadge.text = "SERVICE DISABLED"
            binding.tvStatusBadge.setTextColor(ContextCompat.getColor(this, R.color.status_amber))
            binding.tvStatusTitle.text = getString(R.string.status_inactive)
            binding.tvStatusDesc.text = getString(R.string.service_disabled_desc)
            binding.btnEnableService.visibility = View.VISIBLE
        }
    }

    private fun isAccessibilityServiceEnabled(): Boolean {
        val expectedServiceName = "${packageName}/${AutoScrollAccessibilityService::class.java.canonicalName}"
        val enabledServices = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false

        return enabledServices.split(':').any {
            it.equals(expectedServiceName, ignoreCase = true) ||
            it.contains(AutoScrollAccessibilityService::class.java.simpleName)
        }
    }

    private fun requestBatteryOptimizationExemption() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            if (!powerManager.isIgnoringBatteryOptimizations(packageName)) {
                try {
                    val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                        data = Uri.parse("package:$packageName")
                    }
                    startActivity(intent)
                } catch (e: Exception) {
                    val intent = Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)
                    startActivity(intent)
                }
            } else {
                Toast.makeText(this, "Battery optimization is already disabled!", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun launchYouTubeShorts() {
        val shortsUri = Uri.parse("https://www.youtube.com/shorts")
        val appIntent = Intent(Intent.ACTION_VIEW, shortsUri).apply {
            setPackage("com.google.android.youtube")
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }

        try {
            startActivity(appIntent)
        } catch (_: Exception) {
            // Fallback if YouTube app is not installed
            val webIntent = Intent(Intent.ACTION_VIEW, shortsUri).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            startActivity(webIntent)
        }
    }
}
