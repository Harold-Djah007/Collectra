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
import org.commcare.CommCareApplication;
import org.commcare.android.database.user.models.FormRecord;
import org.commcare.utils.StorageUtils;
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
    private final LatestTaskExecutor<int[]> syncStatusExecutor = new LatestTaskExecutor<>();

    private static final int TYPE_HEADER = 1;
    private final int screenHeight, screenWidth;
    private final int syncButtonPosition;
    private final HashMap<Integer, String> messagePayload = new HashMap<>();
    private final List<HomeCardDisplayData> remainingButtons = new ArrayList<>();

    public HomeScreenAdapter(StandardHomeActivity activity,
                             Vector<String> buttonsToHide,
                             boolean isDemoUser) {
        super(activity);

        this.activity = activity;
        buttonData = HomeButtons.buildButtonData(activity, buttonsToHide, isDemoUser);
        for (HomeCardDisplayData button : buttonData) {
            if (button.imageResource != R.drawable.home_start
                    && button.imageResource != R.drawable.home_saved
                    && button.imageResource != R.drawable.home_incomplete
                    && button.imageResource != R.drawable.home_sync) {
                remainingButtons.add(button);
            }
        }
        syncButtonPosition = -1;

        DisplayMetrics displaymetrics = new DisplayMetrics();
        activity.getWindowManager().getDefaultDisplay().getMetrics(displaymetrics);
        screenHeight = displaymetrics.heightPixels;
        screenWidth = displaymetrics.widthPixels;
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
        return remainingButtons.get(position - 1);
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
        ((TextView)headerHolder.itemView.findViewById(R.id.collectra_workspace_name)).setText(
                CommCareApplication.instance().getCurrentApp().getAppRecord().getDisplayName());

        bindQuickAction(headerHolder.start, R.drawable.home_start);
        bindQuickAction(headerHolder.saved, R.drawable.home_saved);
        bindQuickAction(headerHolder.resume, R.drawable.home_incomplete);
        bindQuickAction(headerHolder.sync, R.drawable.home_sync);
        for (HomeCardDisplayData button : buttonData) {
            if (button.imageResource == R.drawable.home_sync) {
                headerHolder.syncStatus.setOnClickListener(button.subTextListener);
            }
        }
        bindQuickAction(activity.findViewById(R.id.collectra_nav_forms), R.drawable.home_start);
        activity.findViewById(R.id.collectra_nav_home).setOnClickListener(v ->
                activity.findViewById(R.id.nsv_home_screen).scrollTo(0, 0));
        activity.findViewById(R.id.collectra_nav_account).setOnClickListener(v ->
                ((androidx.drawerlayout.widget.DrawerLayout)activity.findViewById(R.id.drawer_layout))
                        .openDrawer(androidx.core.view.GravityCompat.START));
        String currentMessage = messagePayload.get(0);
        if (currentMessage == null) {
            headerHolder.syncStatus.setText(R.string.collectra_today_checking_sync);
        } else {
            headerHolder.syncStatus.setText(currentMessage);
        }
        syncStatusExecutor.submit(
                LifecycleOwnerKt.getLifecycleScope(activity),
                () -> new int[]{SyncDetailCalculations.getNumUnsentForms(),
                        StorageUtils.getNumIncompleteForms(),
                        StorageUtils.getUnsentCompleteOrSavedFormIdsForCurrentApp(
                                CommCareApplication.instance().getUserStorage(FormRecord.class)).size()},
                new LatestTaskExecutor.Callback<>() {
                    @Override
                    public void onResult(int[] counts) {
                        int count = counts[0];
                        if (activity.isFinishing() || activity.isDestroyed()) {
                            return;
                        }
                        ((TextView)headerHolder.resume).setText(activity.getString(
                                R.string.collectra_drafts_count, counts[1]));
                        ((TextView)headerHolder.saved).setText(activity.getString(
                                R.string.collectra_saved_count, counts[2]));
                        String lastSync = SyncDetailCalculations.getLastSyncTimeAndMessage().second;
                        String message = messagePayload.get(0);
                        headerHolder.syncStatus.setText(message != null ? message : count > 0
                                ? activity.getResources().getQuantityString(
                                        R.plurals.collectra_today_waiting_sync, count, count, lastSync)
                                : lastSync);
                    }

                    @Override
                    public void onError(@NonNull Exception exception) {
                        Logger.exception("Could not load home sync status", exception);
                        if (!activity.isFinishing() && !activity.isDestroyed()
                                && messagePayload.get(0) == null) {
                            headerHolder.syncStatus.setText(R.string.collectra_today_sync_unavailable);
                        }
                    }
                });

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
        return remainingButtons.size() + 1;
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
        public final View saved;
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
            saved = itemView.findViewById(R.id.collectra_today_saved);
            resume = itemView.findViewById(R.id.collectra_today_resume);
            sync = itemView.findViewById(R.id.collectra_today_sync);
        }
    }
}
