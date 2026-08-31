package org.commcare.adapters;

import androidx.recyclerview.widget.RecyclerView;
import android.view.View;
import android.widget.RelativeLayout;
import android.widget.TextView;

import org.commcare.dalvik.R;
import org.commcare.views.SquareImageView;

/**
 * Holds views for a home screen button
 *
 * @author Phillip Mates (pmates@dimagi.com).
 */
public class SquareButtonViewHolder extends RecyclerView.ViewHolder {
    public final SquareImageView imageView;
    public final RelativeLayout cardView;
    public final View accentView;
    public final TextView textView;
    public final TextView subTextView;

    public SquareButtonViewHolder(View view) {
        super(view);

        cardView = view.findViewById(R.id.card);
        accentView = view.findViewById(R.id.card_accent);
        imageView = view.findViewById(R.id.card_image);
        textView = view.findViewById(R.id.card_text);
        subTextView = view.findViewById(R.id.card_subtext);
    }
}
