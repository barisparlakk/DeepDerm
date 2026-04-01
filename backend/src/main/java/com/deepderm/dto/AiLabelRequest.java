package com.deepderm.dto;

import com.deepderm.entity.AiLabel;
import jakarta.validation.constraints.NotNull;

public class AiLabelRequest {
    @NotNull private AiLabel.Label label;
    private String parametricValues;

    public AiLabel.Label getLabel() { return label; }
    public void setLabel(AiLabel.Label label) { this.label = label; }
    public String getParametricValues() { return parametricValues; }
    public void setParametricValues(String parametricValues) { this.parametricValues = parametricValues; }
}
