package org.commcare.activities;

import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.text.Spannable;
import android.util.TypedValue;
import android.view.View;
import android.widget.TextView;
import android.widget.Toast;
import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;

import org.commcare.adapters.HomeCardDisplayData;
import org.commcare.adapters.SquareButtonViewHolder;
import org.commcare.dalvik.R;
import org.commcare.google.services.analytics.AnalyticsParamValue;
import org.commcare.google.services.analytics.FirebaseAnalyticsUtil;
import org.commcare.services.CommCareSessionService;
import org.commcare.tasks.LatestTaskExecutor;
import org.commcare.utils.SessionUnavailableException;
import org.commcare.utils.StorageUtils;
import org.commcare.utils.SyncDetailCalculations;
import org.javarosa.core.services.Logger;
import org.javarosa.core.services.locale.Localization;

import java.util.Vector;

import androidx.lifecycle.LifecycleOwnerKt;


/**
 * Build objects that contain all info needed to draw home screen buttons
 *
 * @author Phillip Mates (pmates@dimagi.com).
 */
public class HomeButtons {

    private final static String[] buttonNames =
            new String[]{"start", "training", "saved", "incomplete", "connect", "sync", "report", "logout"};

    private static LatestTaskExecutor<Integer> incompleteFormsExecutor;

    /**
     * Note: The order in which home cards are returned by this method should be consistent with
     * the buttonNames array above
     */
    public static HomeCardDisplayData[] buildButtonData(StandardHomeActivity activity,
                                                        Vector<String> buttonsToHide,
                                                        boolean isDemoUser) {
        String syncKey, homeMessageKey, logoutMessageKey;
        if (!isDemoUser) {
            homeMessageKey = "home.start";
            syncKey = "home.sync";
            logoutMessageKey = "home.logout";
        } else {
            syncKey = "home.sync.demo";
            homeMessageKey = "home.start.demo";
            logoutMessageKey = "home.logout.demo";
        }

        HomeCardDisplayData[] allButtons = new HomeCardDisplayData[]{
                HomeCardDisplayData.homeCardDataWithStaticText(Localization.get(homeMessageKey),
                        R.color.collectra_text_primary,
                        R.drawable.home_start,
                        R.color.collectra_action_start,
                        getStartButtonListener(activity)),
                HomeCardDisplayData.homeCardDataWithStaticText(Localization.get("training.root.title"),
                        R.color.collectra_text_primary,
                        R.drawable.home_training, R.color.collectra_action_training,
                        getTrainingButtonListener(activity)),
                HomeCardDisplayData.homeCardDataWithStaticText(Localization.get("home.forms.saved"),
                        R.color.collectra_text_primary,
                        R.drawable.home_saved,
                        R.color.collectra_action_saved,
                        getViewOldFormsListener(activity)),
                HomeCardDisplayData.homeCardDataWithDynamicText(Localization.get("home.forms.incomplete"),
                        R.color.collectra_text_primary,
                        R.drawable.home_incomplete,
                        R.color.collectra_action_incomplete,
                        getIncompleteButtonListener(activity),
                        null,
                        getIncompleteButtonTextSetter(activity)),
                HomeCardDisplayData.homeCardDataWithStaticText(Localization.get("home.connect"),
                        R.color.collectra_text_primary,
                        R.drawable.quick_reference, R.color.collectra_action_connect,
                        getConnectButtonListener(activity)),
                HomeCardDisplayData.homeCardDataWithNotification(Localization.get(syncKey),
                        R.color.collectra_text_primary,
                        R.color.collectra_text_secondary,
                        R.drawable.home_sync,
                        R.color.collectra_action_sync,
                        R.color.collectra_action_sync,
                        getSyncButtonListener(activity),
                        getSyncButtonSubTextListener(activity),
                        getSyncButtonTextSetter(activity)),
                HomeCardDisplayData.homeCardDataWithStaticText(Localization.get("home.report"),
                        R.color.collectra_text_primary,
                        R.drawable.home_report, R.color.collectra_action_report,
                        getReportButtonListener(activity)),
                HomeCardDisplayData.homeCardDataWithNotification(Localization.get(logoutMessageKey),
                        R.color.collectra_text_primary,
                        R.color.collectra_text_secondary,
                        R.drawable.home_logout, R.color.collectra_action_logout,
                        R.color.collectra_action_logout,
                        getLogoutButtonListener(activity),
                        null,
                        getLogoutButtonTextSetter(activity)),
        };

        return getVisibleButtons(allButtons, buttonsToHide);
    }

    private static HomeCardDisplayData[] getVisibleButtons(HomeCardDisplayData[] allButtons,
                                                           Vector<String> buttonsToHide) {
        int visibleButtonCount = buttonNames.length - buttonsToHide.size();
        HomeCardDisplayData[] buttons = new HomeCardDisplayData[visibleButtonCount];
        int visibleIndex = 0;
        for (int i = 0; i < buttonNames.length; i++) {
            if (!buttonsToHide.contains(buttonNames[i])) {
                buttons[visibleIndex] = allButtons[i];
                visibleIndex++;
            }
        }
        return buttons;
    }

    private static View.OnClickListener getViewOldFormsListener(final StandardHomeActivity activity) {
        return v -> {
            reportButtonClick(AnalyticsParamValue.SAVED_FORMS_BUTTON);
            activity.goToFormArchive(false);
        };
    }

    private static View.OnClickListener getSyncButtonListener(final StandardHomeActivity activity) {
        return v -> {
            if (CommCareSessionService.sessionAliveLock.isLocked()) {
                Toast.makeText(activity, Localization.get("background.sync.user.sync.attempt.during.sync"), Toast.LENGTH_LONG).show();
                return;
            }
            reportButtonClick(AnalyticsParamValue.SYNC_BUTTON);
            activity.syncButtonPressed();
        };
    }

    private static View.OnClickListener getSyncButtonSubTextListener(final StandardHomeActivity activity) {
        return v -> {
            reportButtonClick(AnalyticsParamValue.SYNC_SUBTEXT);
            activity.syncSubTextPressed();
        };
    }

    private static View.OnClickListener getConnectButtonListener(final StandardHomeActivity activity) {
        return v -> {
            reportButtonClick(AnalyticsParamValue.CONNECT_BUTTON);
            activity.userPressedOpportunityStatus();
        };
    }

    private static TextSetter getSyncButtonTextSetter(final StandardHomeActivity activity) {
        return (cardDisplayData, squareButtonViewHolder, context, notificationText) -> {
            try {
                SyncDetailCalculations.updateSubText(activity, squareButtonViewHolder, cardDisplayData,
                        notificationText);
            } catch (SessionUnavailableException e) {
                // stop button setup, since redirection to login is imminent
                return;
            }

            squareButtonViewHolder.subTextView.setVisibility(View.VISIBLE);
            squareButtonViewHolder.subTextView.setBackground(
                    softSubtextChip(context, cardDisplayData.subTextBgColor));
            squareButtonViewHolder.textView.setTextColor(context.getResources().getColor(cardDisplayData.textColor));
            squareButtonViewHolder.textView.setText(cardDisplayData.text);
        };
    }

    private static View.OnClickListener getStartButtonListener(final StandardHomeActivity activity) {
        return v ->  {
            reportButtonClick(AnalyticsParamValue.START_BUTTON);
            activity.enterRootModule();
        };
    }

    private static View.OnClickListener getTrainingButtonListener(final StandardHomeActivity activity) {
        return view -> activity.enterTrainingModule();
    }

    private static View.OnClickListener getIncompleteButtonListener(final StandardHomeActivity activity) {
        return v -> {
            reportButtonClick(AnalyticsParamValue.INCOMPLETE_FORMS_BUTTON);
            activity.goToFormArchive(true);
        };
    }

    private static LatestTaskExecutor<Integer> getIncompleteFormsExecutor() {
        if (incompleteFormsExecutor == null) {
            incompleteFormsExecutor = new LatestTaskExecutor<>();
        }
        return incompleteFormsExecutor;
    }

    private static void updateIncompleteFormsUI(
            StandardHomeActivity activity,
            TextView squareButtonText,
            Integer numIncompleteForms
    ) {
        if (numIncompleteForms > 0) {
            Spannable incompleteIndicator =
                    (activity.localize("home.forms.incomplete.indicator",
                            new String[]{String.valueOf(numIncompleteForms),
                                    Localization.get("home.forms.incomplete")}));
            squareButtonText.setText(incompleteIndicator);
        } else {
            squareButtonText.setText(activity.localize("home.forms.incomplete"));
        }
    }

    private static TextSetter getIncompleteButtonTextSetter(final StandardHomeActivity activity) {
        return (cardDisplayData, squareButtonViewHolder, context, notificationText) -> {
            getIncompleteFormsExecutor().submit(
                    LifecycleOwnerKt.getLifecycleScope(activity),
                    StorageUtils::getNumIncompleteForms,
                    new LatestTaskExecutor.Callback<>() {
                        @Override
                        public void onResult(Integer numIncompleteForms) {
                            if (activity.isFinishing() || activity.isDestroyed()) {
                                return;
                            }
                            updateIncompleteFormsUI(activity, squareButtonViewHolder.textView, numIncompleteForms);
                        }

                        @Override
                        public void onError(@NonNull Exception exception) {
                            if (!(exception instanceof SessionUnavailableException)) {
                                Logger.exception("Failed to retrieve incomplete forms count ", exception);
                            }
                        }
                    });

            squareButtonViewHolder.textView.setTextColor(context.getResources()
                    .getColor(cardDisplayData.textColor));
            squareButtonViewHolder.subTextView.setVisibility(View.GONE);
        };
    }

    private static View.OnClickListener getLogoutButtonListener(final StandardHomeActivity activity) {
        return v -> {
            reportButtonClick(AnalyticsParamValue.LOGOUT_BUTTON);
            activity.userTriggeredLogout();
        };
    }

    private static TextSetter getLogoutButtonTextSetter(final StandardHomeActivity activity) {
        return (cardDisplayData, squareButtonViewHolder, context, notificationText) -> {
            squareButtonViewHolder.textView.setText(cardDisplayData.text);
            squareButtonViewHolder.textView.setTextColor(context.getResources().getColor(cardDisplayData.textColor));
            squareButtonViewHolder.subTextView.setVisibility(View.VISIBLE);
            squareButtonViewHolder.subTextView.setText(activity.getActivityTitle());
            squareButtonViewHolder.subTextView.setTextColor(context.getResources().getColor(cardDisplayData.subTextColor));
            squareButtonViewHolder.subTextView.setBackground(
                    softSubtextChip(context, cardDisplayData.subTextBgColor));
        };
    }

    private static Drawable softSubtextChip(Context context, int colorResource) {
        float radius = TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP,
                10f,
                context.getResources().getDisplayMetrics()
        );
        int accent = ContextCompat.getColor(context, colorResource);
        int soft = Color.argb(
                36,
                Color.red(accent),
                Color.green(accent),
                Color.blue(accent)
        );
        GradientDrawable chip = new GradientDrawable();
        chip.setShape(GradientDrawable.RECTANGLE);
        chip.setCornerRadius(radius);
        chip.setColor(soft);
        return chip;
    }

    private static View.OnClickListener getReportButtonListener(final StandardHomeActivity activity) {
        return v -> {
            reportButtonClick(AnalyticsParamValue.REPORT_BUTTON);
            Intent i = new Intent(activity, ReportProblemActivity.class);
            activity.startActivity(i);
        };
    }

    private static void reportButtonClick(String buttonLabel) {
        FirebaseAnalyticsUtil.reportHomeButtonClick(buttonLabel);
    }

    public interface TextSetter {
        /**
         * Set view holder's text and subtext either from provided display
         * data, notification text argument, or auxiliary computations
         *
         * @param notificationText Optional text which will always be used when provided
         */
        void update(HomeCardDisplayData cardDisplayData,
                    SquareButtonViewHolder squareButtonViewHolder,
                    Context context,
                    String notificationText);
    }
}
