package com.deepderm.dto;

import jakarta.validation.constraints.NotBlank;

public class NoteRequest {
    @NotBlank private String noteText;

    public String getNoteText() { return noteText; }
    public void setNoteText(String noteText) { this.noteText = noteText; }
}
