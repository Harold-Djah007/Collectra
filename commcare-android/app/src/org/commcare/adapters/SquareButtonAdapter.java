package org.commcare.adapters;

import android.content.Context;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;

import androidx.core.content.ContextCompat;
import androidx.recyclerview.widget.RecyclerView;
import android.util.TypedValue;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

import org.commcare.dalvik.R;
import org.commcare.views.CollectraMotion;

import java.util.List;

/**
 * Inflation and binding of Collectra home action rows.
 *
 * @author Phillip Mates (pmates@dimagi.com).
 */
abstract class SquareButtonAdapter
        extends RecyclerView.Adapter<RecyclerView.ViewHolder> {

    final Context context;

    private static final int TYPE_BUTTON = 0;

    SquareButtonAdapter(Context context) {
        this.context = context;
    }

    @Override
    public RecyclerView.ViewHolder onCreateViewHolder(ViewGroup parent, int viewType) {
        final LayoutInflater inflater = LayoutInflater.from(parent.getContext());

        if (viewType == TYPE_BUTTON) {
            View layoutView = inflater.inflate(R.layout.square_card, parent, false);
            return new SquareButtonViewHolder(layoutView);
        } else {
            throw new RuntimeException("No " + viewType + " view type exists");
        }
    }

    @Override
    public void onBindViewHolder(RecyclerView.ViewHolder holder, int i) {
        if (holder instanceof SquareButtonViewHolder) {
            bindCard((SquareButtonViewHolder)holder, i, null);
        } else {
            throw new RuntimeException("Unable to bind ViewHolder of type: " + holder.getClass());
        }
    }

    @Override
    public void onBindViewHolder(RecyclerView.ViewHolder holder,
                                 int i, List<Object> payload) {
        if (holder instanceof SquareButtonViewHolder) {
            bindCard((SquareButtonViewHolder)holder, i, payload);
        } else {
            throw new RuntimeException("Unable to bind ViewHolder of type: " + holder.getClass());
        }
    }

    private void bindCard(SquareButtonViewHolder squareButtonViewHolder,
                          int i, List<Object> payload) {
        HomeCardDisplayData cardDisplayData = getItem(i);
        String notificationText = null;

        if (payload != null) {
            notificationText = getFirstPayloadString(payload);
        }

        cardDisplayData.textSetter.update(cardDisplayData,
                squareButtonViewHolder, context, notificationText);
        setupViewHolder(context, cardDisplayData, squareButtonViewHolder, i);
    }

    /**
     * Get nth data element in adapter.
     */
    protected abstract HomeCardDisplayData getItem(int position);

    /**
     * Get 1st string in payload list, which is constructed from payloads
     * provided on calls to notify item/data set changed.
     */
    private static String getFirstPayloadString(List<Object> payloadList) {
        String lastPayloadString = null;
        for (Object entry : payloadList) {
            if (entry instanceof String) {
                lastPayloadString = (String)entry;
            }
        }
        return lastPayloadString;
    }

    private static void setupViewHolder(Context context,
                                        HomeCardDisplayData cardDisplayData,
                                        SquareButtonViewHolder squareButtonViewHolder) {
        final Drawable buttonDrawable =
                ContextCompat.getDrawable(context, cardDisplayData.imageResource);
        squareButtonViewHolder.imageView.setImageDrawable(buttonDrawable);
        squareButtonViewHolder.cardView.setOnClickListener(cardDisplayData.listener);

        if (cardDisplayData.subTextListener != null) {
            squareButtonViewHolder.subTextView.setOnClickListener(cardDisplayData.subTextListener);
        }

        // Soft Collectra row; ink chip + signal/accent rail for identity.
        squareButtonViewHolder.cardView.setBackground(
                ContextCompat.getDrawable(context, R.drawable.collectra_home_card_surface));
        squareButtonViewHolder.iconChip.setBackground(
                accentChipDrawable(context, R.color.collectra_ink));
        if (squareButtonViewHolder.accentRail != null) {
            squareButtonViewHolder.accentRail.setBackgroundColor(
                    ContextCompat.getColor(context, cardDisplayData.bgColor));
        }

        // Staggered chip pulse so tiles feel alive like the brand mark.
        long delay = Math.max(0, squareButtonViewHolder.getBindingAdapterPosition()) * 90L;
        CollectraMotion.startChipPulse(squareButtonViewHolder.iconChip, delay);

        squareButtonViewHolder.textView.setAlpha(0.85f);
        squareButtonViewHolder.textView.animate()
                .alpha(1f)
                .setDuration(280)
                .start();
    }

    private static GradientDrawable accentChipDrawable(Context context, int bgColorResource) {
        float radius = TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP,
                14f,
                context.getResources().getDisplayMetrics()
        );
        GradientDrawable chip = new GradientDrawable();
        chip.setShape(GradientDrawable.RECTANGLE);
        chip.setCornerRadius(radius);
        chip.setColor(ContextCompat.getColor(context, bgColorResource));
        return chip;
    }

    @Override
    public int getItemViewType(int position) {
        return TYPE_BUTTON;
    }
}
