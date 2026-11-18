package com.characterverse.core.design

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color

/** Tokens mirrored from shared/design-tokens/tokens.json (same values as iOS). */
object Tokens {
    val brand = hex("#6C4DF6")
    val brandSecondary = hex("#00C2A8")
    val accent = hex("#FFB547")
    val danger = hex("#E5484D")
    val success = hex("#30A46C")
    val warning = hex("#F5A524")
    val heroGradient = Brush.linearGradient(listOf(brand, brandSecondary))
    private val categories = mapOf("hero" to "#3E7BFA", "villain" to "#8E4EC6", "cartoon" to "#FF8A3D", "fantasy" to "#30A46C",
        "robot" to "#7C8798", "alien" to "#00B3A4", "creature" to "#D6409F")
    fun category(id: String) = hex(categories[id] ?: "#6C4DF6")
}

fun hex(value: String): Color {
    val v = value.removePrefix("#").toLong(16)
    return Color(red = ((v shr 16) and 0xFF).toInt(), green = ((v shr 8) and 0xFF).toInt(), blue = (v and 0xFF).toInt())
}

fun Color.toHex(): String = "#%02X%02X%02X".format((red * 255).toInt(), (green * 255).toInt(), (blue * 255).toInt())

@Composable
fun CharacterVerseTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val colors = if (dark) darkColorScheme(primary = Tokens.brand, secondary = Tokens.brandSecondary, tertiary = Tokens.accent,
        background = hex("#0F0D1A"), surface = hex("#1C1930"), surfaceVariant = hex("#2A2645"), error = Tokens.danger)
    else lightColorScheme(primary = Tokens.brand, secondary = Tokens.brandSecondary, tertiary = Tokens.accent,
        background = hex("#F7F5FF"), surface = Color.White, surfaceVariant = hex("#EFEBFF"), error = Tokens.danger,
        onSurfaceVariant = hex("#5C5873"))
    MaterialTheme(colorScheme = colors, content = content)
}
