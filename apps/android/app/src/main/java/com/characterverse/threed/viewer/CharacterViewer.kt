package com.characterverse.threed.viewer

import android.provider.Settings
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import com.characterverse.core.design.hex
import com.characterverse.domain.usecase.ResolvedPart
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * Lightweight 3D preview: a software renderer that rotates the shared procedural parts around Y, depth-sorts them
 * and shades each primitive. Interprets exactly the same part list as iOS SceneKit and the backend GLB (ADR 0001).
 * Filament replaces this once authored GLB assets ship.
 */
@Composable
fun CharacterViewer(parts: List<ResolvedPart>, modifier: Modifier = Modifier, background: Color = hex("#EDE9FF"),
                    autoRotate: Boolean = true, description: String = "Character preview") {
    val reduceMotion = rememberReduceMotion()
    var dragAngle by remember { mutableFloatStateOf(0f) }
    val spin = if (autoRotate && !reduceMotion) {
        val t = rememberInfiniteTransition(label = "spin")
        t.animateFloat(0f, (2 * Math.PI).toFloat(), infiniteRepeatable(tween(14000, easing = LinearEasing), RepeatMode.Restart), label = "a").value
    } else 0.35f
    Box(modifier.semantics { contentDescription = "$description. Drag to rotate." }) {
        Canvas(Modifier.matchParentSize().pointerInput(Unit) { detectDragGestures { _, d -> dragAngle += d.x / 120f } }) {
            drawRect(Brush.verticalGradient(listOf(background, Color.White)))
            drawCharacter(parts, spin + dragAngle, Offset(size.width / 2, size.height * 0.9f), fitScale(parts, size))
        }
    }
}

fun fitScale(parts: List<ResolvedPart>, size: Size, fill: Float = 0.8f): Float {
    if (parts.isEmpty()) return 1f
    val top = parts.maxOf { it.position[1] + it.size[1] / 2 }.toFloat()
    val width = parts.maxOf { max(abs(it.position[0]), abs(it.position[2])) + it.size[0] / 2 }.toFloat() * 2
    return min(size.height * fill / top, size.width * fill / width)
}

fun DrawScope.drawCharacter(parts: List<ResolvedPart>, angle: Float, feet: Offset, scale: Float, light: Color = Color.White, flat: Boolean = false) {
    val c = cos(angle); val s = sin(angle)
    drawOval(Color.Black.copy(alpha = 0.08f), Offset(feet.x - scale * 0.5f, feet.y - scale * 0.07f), Size(scale, scale * 0.14f))
    data class P(val part: ResolvedPart, val x: Float, val y: Float, val z: Float, val w: Float, val h: Float)
    val projected = parts.map { p ->
        val x = p.position[0].toFloat(); val z = p.position[2].toFloat()
        val rx = if (flat) x else x * c + z * s
        val rz = if (flat) z else -x * s + z * c
        val sx = p.size[0].toFloat(); val sz = p.size[2].toFloat()
        val w = if (flat) sx else abs(sx * c) + abs(sz * s)
        P(p, rx, p.position[1].toFloat(), rz, w, p.size[1].toFloat())
    }.sortedBy { it.z }
    for (p in projected) {
        val cx = feet.x + p.x * scale
        val cy = feet.y - p.y * scale
        val w = max(p.w * scale, 1f); val h = max(p.h * scale, 1f)
        val topLeft = Offset(cx - w / 2, cy - h / 2)
        val base = hex(p.part.color).let { Color(it.red * light.red, it.green * light.green, it.blue * light.blue) }
        val shadeBrush = Brush.radialGradient(listOf(lighten(base, 0.28f), base, darken(base, 0.72f)),
            center = Offset(cx - w * 0.2f, cy - h * 0.25f), radius = max(w, h) * 0.85f)
        val outline = darken(base, 0.55f)
        when (p.part.shape) {
            "sphere" -> { drawOval(shadeBrush, topLeft, Size(w, h)); drawOval(outline, topLeft, Size(w, h), style = Stroke(1.2f)) }
            "capsule" -> { drawRoundRect(shadeBrush, topLeft, Size(w, h), CornerRadius(min(w, h) / 2)); drawRoundRect(outline, topLeft, Size(w, h), CornerRadius(min(w, h) / 2), style = Stroke(1.2f)) }
            "cone" -> {
                val path = Path().apply { moveTo(cx - w / 2, cy + h / 2); lineTo(cx + w / 2, cy + h / 2); lineTo(cx, cy - h / 2); close() }
                drawPath(path, shadeBrush); drawPath(path, outline, style = Stroke(1.2f))
            }
            "cylinder" -> {
                drawRect(shadeBrush, topLeft, Size(w, h))
                drawOval(lighten(base, 0.2f), Offset(cx - w / 2, cy - h / 2 - w * 0.12f), Size(w, w * 0.24f))
            }
            else -> { drawRoundRect(shadeBrush, topLeft, Size(w, h), CornerRadius(min(w, h) * 0.18f)); drawRoundRect(outline, topLeft, Size(w, h), CornerRadius(min(w, h) * 0.18f), style = Stroke(1.2f)) }
        }
    }
}

private fun lighten(c: Color, f: Float) = Color(c.red + (1 - c.red) * f, c.green + (1 - c.green) * f, c.blue + (1 - c.blue) * f)
private fun darken(c: Color, f: Float) = Color(c.red * f, c.green * f, c.blue * f)

/** Small static thumbnail (lists/cards). */
@Composable
fun CharacterThumbnail(parts: List<ResolvedPart>, modifier: Modifier = Modifier) {
    Canvas(modifier) { drawCharacter(parts, 0.3f, Offset(size.width / 2, size.height * 0.93f), fitScale(parts, size, 0.84f)) }
}

@Composable
fun rememberReduceMotion(): Boolean {
    val context = LocalContext.current
    return remember {
        runCatching { Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f }.getOrDefault(false)
    }
}
