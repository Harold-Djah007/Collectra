package org.commcare.views.widgets;

import org.javarosa.form.api.FormEntryPrompt;
import org.junit.Test;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

public class QuestionWidgetLabelTest {

    @Test
    public void showsMarkdownQuestionWhenPlainTextIsAbsent() {
        FormEntryPrompt prompt = mock(FormEntryPrompt.class);
        when(prompt.getMarkdownText()).thenReturn("Inspect drying bed 1");

        assertTrue(QuestionWidget.hasQuestionText(prompt));
    }

    @Test
    public void hidesQuestionWithoutAnyLabel() {
        FormEntryPrompt prompt = mock(FormEntryPrompt.class);

        assertFalse(QuestionWidget.hasQuestionText(prompt));
    }
}
