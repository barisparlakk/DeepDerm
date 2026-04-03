package com.deepderm.repository;

import com.deepderm.entity.AiLabel;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface AiLabelRepository extends JpaRepository<AiLabel, UUID> {
}
