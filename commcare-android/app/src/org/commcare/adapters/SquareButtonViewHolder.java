package org.commcare.adapters;

import androidx.recyclerview.widget.RecyclerView;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.RelativeLayout;
import android.widget.TextView;

import org.commcare.dalvik.R;

/**
 * Holds views for a home screen action row
 *
 * @author Phillip Mates (pmates@dimagi.com).
 */
public class SquareButtonViewHolder extends RecyclerView.ViewHolder {
    public final ImageView imageView;
    public final FrameLayout iconChip;
    public final RelativeLayout cardView;
    public final TextView textView;
    public final TextView subTextView;

    public SquareButtonViewHolder(View view) {
        super(view);

        cardView = view.findViewById(R.id.card);
        iconChip = view.findViewById(R.id.card_icon_chip);
        imageView = view.findViewById(R.id.card_image);
        textView = view.findViewById(R.id.card_text);
        subTextView = view.findViewById(R.id.card_subtext);
    }
}
