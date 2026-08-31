package org.commcare.views;

import android.animation.AnimatorSet;
import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.view.View;
import android.view.animation.AccelerateDecelerateInterpolator;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.OvershootInterpolator;

import androidx.annotation.Nullable;

import org.commcare.dalvik.R;

/**
 * Lightweight Collectra motion helpers for brand liveliness without noisy effects.
 */
public final class CollectraMotion {

    private CollectraMotion() {
    }

    /** Soft fade + rise used when a screen first appears. */
    public static void playScreenEnter(@Nullable View root) {
        if (root == null) {
            return;
        }
        root.setAlpha(0f);
        root.setTranslationY(28f);
        root.animate()
                .alpha(1f)
                .translationY(0f)
                .setDuration(520)
                .setInterpolator(new DecelerateInterpolator(1.6f))
                .start();
    }

    /**
     * Continues the Collectra launch screen after the system splash.
     * The mark stays visible (matching {@code collectra_launch_window}) so cold start
     * does not look like a second splash; title/tagline animate in on top.
     */
    public static void playLaunchSplash(@Nullable View mark,
                                        @Nullable View title,
                                        @Nullable View tagline) {
        if (mark != null) {
            mark.setAlpha(1f);
            mark.setScaleX(1f);
            mark.setScaleY(1f);
            startLogoPulse(mark);
        }
        playWordmarkEnter(title);
        if (title != null) {
            title.postDelayed(() -> startSoftFloat(title), 420);
        }
        if (tagline != null) {
            tagline.setAlpha(0f);
            tagline.animate()
                    .alpha(1f)
                    .setStartDelay(160)
                    .setDuration(420)
                    .start();
        }
    }

    /** Breathing pulse for the Collectra mark. */
    public static void startLogoPulse(@Nullable View logo) {
        if (logo == null) {
            return;
        }
        logo.clearAnimation();
        ObjectAnimator scaleX = ObjectAnimator.ofFloat(logo, View.SCALE_X, 1f, 1.12f, 1f);
        ObjectAnimator scaleY = ObjectAnimator.ofFloat(logo, View.SCALE_Y, 1f, 1.12f, 1f);
        ObjectAnimator rotate = ObjectAnimator.ofFloat(logo, View.ROTATION, 0f, -6f, 6f, 0f);
        scaleX.setRepeatCount(ValueAnimator.INFINITE);
        scaleY.setRepeatCount(ValueAnimator.INFINITE);
        rotate.setRepeatCount(ValueAnimator.INFINITE);
        AnimatorSet set = new AnimatorSet();
        set.playTogether(scaleX, scaleY, rotate);
        set.setDuration(2200);
        set.setInterpolator(new AccelerateDecelerateInterpolator());
        set.start();
        logo.setTag(R.id.collectra_motion_tag, set);
    }

    /** Title pops in with a slight overshoot, then floats gently. */
    public static void startTitleLiveliness(@Nullable View title) {
        if (title == null) {
            return;
        }
        title.setAlpha(0f);
        title.setScaleX(0.92f);
        title.setScaleY(0.92f);
        title.setTranslationY(16f);
        title.animate()
                .alpha(1f)
                .scaleX(1f)
                .scaleY(1f)
                .translationY(0f)
                .setDuration(480)
                .setInterpolator(new OvershootInterpolator(1.4f))
                .withEndAction(() -> startSoftFloat(title))
                .start();
    }

    /** Slow vertical float so titles feel alive like the icon chips. */
    public static void startSoftFloat(@Nullable View view) {
        if (view == null) {
            return;
        }
        ObjectAnimator floatY = ObjectAnimator.ofFloat(view, View.TRANSLATION_Y, 0f, -4f, 0f);
        floatY.setDuration(2600);
        floatY.setRepeatCount(ValueAnimator.INFINITE);
        floatY.setInterpolator(new AccelerateDecelerateInterpolator());
        floatY.start();
        view.setTag(R.id.collectra_motion_tag, floatY);
    }

    /** Accent bar grows in from the left. */
    public static void playAccentReveal(@Nullable View accent) {
        if (accent == null) {
            return;
        }
        accent.setScaleX(0f);
        accent.setPivotX(0f);
        accent.animate()
                .scaleX(1f)
                .setDuration(560)
                .setStartDelay(180)
                .setInterpolator(new DecelerateInterpolator(1.4f))
                .start();
    }

    /** Tile icon chip subtle pulse so actions feel tactile. */
    public static void startChipPulse(@Nullable View chip, long startDelayMs) {
        if (chip == null) {
            return;
        }
        ObjectAnimator scaleX = ObjectAnimator.ofFloat(chip, View.SCALE_X, 1f, 1.06f, 1f);
        ObjectAnimator scaleY = ObjectAnimator.ofFloat(chip, View.SCALE_Y, 1f, 1.06f, 1f);
        scaleX.setRepeatCount(ValueAnimator.INFINITE);
        scaleY.setRepeatCount(ValueAnimator.INFINITE);
        scaleX.setStartDelay(startDelayMs);
        scaleY.setStartDelay(startDelayMs);
        AnimatorSet set = new AnimatorSet();
        set.playTogether(scaleX, scaleY);
        set.setDuration(2400);
        set.setInterpolator(new AccelerateDecelerateInterpolator());
        set.start();
        chip.setTag(R.id.collectra_motion_tag, set);
    }

    /** Brand wordmark fades/slides beside the logo. */
    public static void playWordmarkEnter(@Nullable View wordmark) {
        if (wordmark == null) {
            return;
        }
        wordmark.setAlpha(0f);
        wordmark.setTranslationX(-12f);
        wordmark.animate()
                .alpha(1f)
                .translationX(0f)
                .setDuration(420)
                .setStartDelay(80)
                .setInterpolator(new DecelerateInterpolator())
                .start();
    }
}
