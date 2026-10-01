package org.commcare.adapters;

import androidx.recyclerview.widget.RecyclerView;
import androidx.lifecycle.LifecycleOwnerKt;
import androidx.annotation.NonNull;
import android.util.DisplayMetrics;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageView;
import android.widget.TextView;

import org.commcare.activities.StandardHomeActivity;
import org.commcare.activities.HomeButtons;
import org.commcare.dalvik.R;
import org.commcare.views.CollectraMotion;
import org.commcare.views.CustomBanner;
import org.commcare.tasks.LatestTaskExecutor;
import org.commcare.utils.SyncDetailCalculations;
import org.javarosa.core.services.Logger;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Vector;

/**
 * Shows Collectra home actions with a lively brand masthead.
 *
 * @author Phillip Mates (pmates@dimagi.com)
 */
public class HomeScreenAdapter
        extends SquareButtonAdapter {

    private final HomeCardDisplayData[] buttonData;
    private final StandardHomeActivity activity;
    private final LatestTaskExecutor<Integer> syncStatusExecutor = new LatestTaskExecutor<>();

    private static final int TYPE_HEADER = 1;
    private final int screenHeight, screenWidth;
    private final int syncButtonPosition;
    private final HashMap<Integer, String> messagePayload = new HashMap<>();
    private boolean mastheadAnimated;

    public HomeScreenAdapter(StandardHomeActivity activity,
                             Vector<String> buttonsToHide,
                             boolean isDemoUser) {
        super(activity);

        this.activity = activity;
        buttonData = HomeButtons.buildButtonData(activity, buttonsToHide, isDemoUser);
        syncButtonPosition = calcSyncButtonPos();

        DisplayMetrics displaymetrics = new DisplayMetrics();
        activity.getWindowManager().getDefaultDisplay().getMetrics(displaymetrics);
        screenHeight = displaymetrics.heightPixels;
        screenWidth = displaymetrics.widthPixels;
    }

    private int calcSyncButtonPos() {
        for (int i = 0; i < buttonData.length; i++) {
            if (buttonData[i].imageResource == R.drawable.home_sync) {
                return i + 1;
            }
        }
        return -1;
    }

    @Override
    public RecyclerView.ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        if (viewType == TYPE_HEADER) {
            final LayoutInflater inflater = LayoutInflater.from(parent.getContext());
            View header = inflater.inflate(R.layout.collectra_home_masthead, parent, false);
            return new HeaderViewHolder(header);
        } else {
            return super.onCreateViewHolder(parent, viewType);
        }
    }

    @Override
    public void onBindViewHolder(RecyclerView.ViewHolder holder, int i, List<Object> payload) {
        if (holder instanceof HeaderViewHolder) {
            bindHeader((HeaderViewHolder)holder);
        } else {
            if (payload == null || payload.isEmpty()) {
                payload = new ArrayList<>();
                payload.add(messagePayload.remove(i));
            }

            super.onBindViewHolder(holder, i, payload);
        }
    }

    @Override
    public void onBindViewHolder(RecyclerView.ViewHolder holder, int i) {
        if (holder instanceof HeaderViewHolder) {
            bindHeader((HeaderViewHolder)holder);
        } else {
            ArrayList<Object> payload = new ArrayList<>();
            payload.add(messagePayload.remove(i));

            super.onBindViewHolder(holder, i, payload);
        }
    }

    @Override
    protected HomeCardDisplayData getItem(int position) {
        return buttonData[position - 1];
    }

    private void bindHeader(HeaderViewHolder headerHolder) {
        ViewGroup.LayoutParams layoutParams = headerHolder.itemView.getLayoutParams();
        layoutParams.width = ViewGroup.LayoutParams.MATCH_PARENT;
        headerHolder.itemView.setLayoutParams(layoutParams);

        boolean usedCustom = CustomBanner.useCustomBanner(
                context,
                screenHeight,
                screenWidth,
                headerHolder.customBanner,
                CustomBanner.Banner.HOME
        );
        headerHolder.customBanner.setVisibility(
                usedCustom ? View.VISIBLE : View.GONE
        );
        headerHolder.headerImage.setImageResource(R.drawable.collectra_mark);

        bindQuickAction(headerHolder.start, R.drawable.home_start);
        bindQuickAction(headerHolder.resume, R.drawable.home_incomplete);
        bindQuickAction(headerHolder.sync, R.drawable.home_sync);
        headerHolder.syncStatus.setText(R.string.collectra_today_checking_sync);
        syncStatusExecutor.submit(
                LifecycleOwnerKt.getLifecycleScope(activity),
                SyncDetailCalculations::getNumUnsentForms,
                new LatestTaskExecutor.Callback<>() {
                    @Override
                    public void onResult(Integer count) {
                        if (activity.isFinishing() || activity.isDestroyed()) {
                            return;
                        }
                        String lastSync = SyncDetailCalculations.getLastSyncTimeAndMessage().second;
                        headerHolder.syncStatus.setText(count > 0
                                ? activity.getResources().getQuantityString(
                                        R.plurals.collectra_today_waiting_sync, count, count, lastSync)
                                : lastSync);
                    }

                    @Override
                    public void onError(@NonNull Exception exception) {
                        Logger.exception("Could not load home sync status", exception);
                        if (!activity.isFinishing() && !activity.isDestroyed()) {
                            headerHolder.syncStatus.setText(R.string.collectra_today_sync_unavailable);
                        }
                    }
                });

        if (!mastheadAnimated) {
            mastheadAnimated = true;
            CollectraMotion.startLogoPulse(headerHolder.headerImage);
            CollectraMotion.playWordmarkEnter(headerHolder.wordmark);
            CollectraMotion.startTitleLiveliness(headerHolder.greeting);
            CollectraMotion.playAccentReveal(headerHolder.accent);
            if (headerHolder.tagline != null) {
                headerHolder.tagline.setAlpha(0f);
                headerHolder.tagline.animate()
                        .alpha(1f)
                        .setStartDelay(220)
                        .setDuration(360)
                        .start();
            }
        }
    }

    private void bindQuickAction(View action, int imageResource) {
        for (HomeCardDisplayData button : buttonData) {
            if (button.imageResource == imageResource) {
                action.setVisibility(View.VISIBLE);
                action.setOnClickListener(button.listener);
                return;
            }
        }
        action.setVisibility(View.GONE);
        action.setOnClickListener(null);
    }

    @Override
    public int getItemCount() {
        return buttonData.length + 1;
    }

    @Override
    public int getItemViewType(int position) {
        if (isPositionHeader(position)) {
            return TYPE_HEADER;
        } else {
            return super.getItemViewType(position);
        }
    }

    private boolean isPositionHeader(int position) {
        return position == 0;
    }

    public int getSyncButtonPosition() {
        return syncButtonPosition;
    }

    public void setMessagePayload(int position, String message) {
        messagePayload.put(position, message);
    }

    private static class HeaderViewHolder extends RecyclerView.ViewHolder {
        public final ImageView headerImage;
        public final ImageView customBanner;
        public final TextView wordmark;
        public final TextView greeting;
        public final TextView tagline;
        public final View accent;
        public final TextView syncStatus;
        public final View start;
        public final View resume;
        public final View sync;

        public HeaderViewHolder(View itemView) {
            super(itemView);
            headerImage = itemView.findViewById(R.id.main_top_banner);
            customBanner = itemView.findViewById(
                    R.id.collectra_custom_home_banner
            );
            wordmark = itemView.findViewById(R.id.collectra_home_wordmark);
            greeting = itemView.findViewById(R.id.collectra_home_greeting);
            tagline = itemView.findViewById(R.id.collectra_home_tagline);
            accent = itemView.findViewById(R.id.collectra_home_accent);
            syncStatus = itemView.findViewById(R.id.collectra_today_sync_status);
            start = itemView.findViewById(R.id.collectra_today_start);
            resume = itemView.findViewById(R.id.collectra_today_resume);
            sync = itemView.findViewById(R.id.collectra_today_sync);
        }
    }
}
