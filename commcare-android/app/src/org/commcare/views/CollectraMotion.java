package org.commcare.views;

import android.animation.Animator;
import android.animation.AnimatorListenerAdapter;
import android.animation.AnimatorSet;
import android.animation.ObjectAnimator;
import android.view.View;
import android.view.animation.AccelerateDecelerateInterpolator;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.OvershootInterpolator;

import androidx.annotation.Nullable;

import org.commcare.dalvik.R;

public final class CollectraMotion {

    private CollectraMotion() {
    }

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
        if (tagline != null) {
            tagline.setAlpha(0f);
            tagline.animate()
                    .alpha(1f)
                    .setStartDelay(160)
                    .setDuration(420)
                    .start();
        }
    }

    public static void startLogoPulse(@Nullable View logo) {
        if (logo == null) {
            return;
        }
        logo.clearAnimation();
        ObjectAnimator scaleX = ObjectAnimator.ofFloat(logo, View.SCALE_X, 1f, 1.12f, 1f);
        ObjectAnimator scaleY = ObjectAnimator.ofFloat(logo, View.SCALE_Y, 1f, 1.12f, 1f);
        ObjectAnimator rotate = ObjectAnimator.ofFloat(logo, View.ROTATION, 0f, -6f, 6f, 0f);
        AnimatorSet set = new AnimatorSet();
        set.playTogether(scaleX, scaleY, rotate);
        set.setDuration(820);
        set.setInterpolator(new AccelerateDecelerateInterpolator());
        startTracked(logo, set);
    }

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
                .start();
    }

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

    public static void startChipPulse(@Nullable View chip, long startDelayMs) {
        if (chip == null) {
            return;
        }
        ObjectAnimator scaleX = ObjectAnimator.ofFloat(chip, View.SCALE_X, 1f, 1.06f, 1f);
        ObjectAnimator scaleY = ObjectAnimator.ofFloat(chip, View.SCALE_Y, 1f, 1.06f, 1f);
        scaleX.setStartDelay(startDelayMs);
        scaleY.setStartDelay(startDelayMs);
        AnimatorSet set = new AnimatorSet();
        set.playTogether(scaleX, scaleY);
        set.setDuration(900);
        set.setInterpolator(new AccelerateDecelerateInterpolator());
        startTracked(chip, set);
    }

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

    private static void startTracked(View view, Animator animator) {
        Object existing = view.getTag(R.id.collectra_motion_tag);
        if (existing instanceof Animator) {
            ((Animator) existing).cancel();
        }
        view.setTag(R.id.collectra_motion_tag, animator);
        animator.addListener(new AnimatorListenerAdapter() {
            @Override
            public void onAnimationEnd(Animator animation) {
                if (view.getTag(R.id.collectra_motion_tag) == animation) {
                    view.setTag(R.id.collectra_motion_tag, null);
                }
            }
        });
        animator.start();
    }
}
