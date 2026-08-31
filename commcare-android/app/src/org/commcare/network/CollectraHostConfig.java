package org.commcare.network;

import android.net.Uri;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import org.commcare.dalvik.BuildConfig;

import java.net.InetAddress;
import java.net.UnknownHostException;
import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Central Collectra HQ connectivity helpers used by install, sync diagnostics, and SMS allowlists.
 */
public final class CollectraHostConfig {

    public static final String DEFAULT_ACCOUNT_ROOT = "commcarehq.org";
    private static final Pattern COMMCARE_HQ_HOST =
            Pattern.compile("(?:^|\\.)commcarehq\\.org$", Pattern.CASE_INSENSITIVE);

    private CollectraHostConfig() {
    }

    @NonNull
    public static String getConfiguredBaseUrl() {
        return normalizeBaseUrl(BuildConfig.COLLECTRA_HQ_BASE_URL);
    }

    public static boolean isConfigured() {
        return !getConfiguredBaseUrl().isEmpty();
    }

    @NonNull
    public static String getAccountRoot() {
        return DEFAULT_ACCOUNT_ROOT;
    }

    @Nullable
    public static String getConfiguredHost() {
        String base = getConfiguredBaseUrl();
        if (base.isEmpty()) {
            return null;
        }
        try {
            return Uri.parse(base).getHost();
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * Resolve a typed/scanned install reference against Collectra HQ when needed.
     */
    @NonNull
    public static String resolveInstallReference(@Nullable String reference) {
        if (reference == null) {
            return "";
        }
        return AppInstallCodeResolver.resolve(reference, getConfiguredBaseUrl());
    }

    @NonNull
    public static String getFallbackPostUrl(@NonNull String legacyDefault) {
        String base = getConfiguredBaseUrl();
        if (base.isEmpty()) {
            return legacyDefault;
        }
        return base + "/receiver/submit/pf";
    }

    @NonNull
    public static String getFallbackRestoreUrl(@NonNull String legacyDefault) {
        String base = getConfiguredBaseUrl();
        if (base.isEmpty()) {
            return legacyDefault;
        }
        return base + "/a/phone/restore";
    }

    @NonNull
    public static String getServerUpUrl(@NonNull String legacyDefault) {
        String base = getConfiguredBaseUrl();
        if (base.isEmpty()) {
            return legacyDefault;
        }
        return base + "/serverup.txt";
    }

    public static boolean isAllowedSmsInstallHost(@Nullable String host) {
        if (host == null || host.isEmpty()) {
            return false;
        }
        String normalized = host.toLowerCase(Locale.US);
        if (COMMCARE_HQ_HOST.matcher(normalized).find()) {
            return true;
        }
        String configuredHost = getConfiguredHost();
        if (configuredHost != null && configuredHost.equalsIgnoreCase(host)) {
            return true;
        }
        return isLocalOrPrivateHost(normalized);
    }

    @NonNull
    static String normalizeBaseUrl(@Nullable String raw) {
        if (raw == null) {
            return "";
        }
        String trimmed = raw.trim();
        while (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed;
    }

    private static boolean isLocalOrPrivateHost(String host) {
        if ("localhost".equals(host) || "127.0.0.1".equals(host) || "::1".equals(host)) {
            return true;
        }
        try {
            InetAddress address = InetAddress.getByName(host);
            return address.isSiteLocalAddress()
                    || address.isLoopbackAddress()
                    || address.isLinkLocalAddress();
        } catch (UnknownHostException e) {
            return false;
        }
    }
}
