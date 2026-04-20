package com.deepderm;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@SpringBootApplication
@EnableAsync
public class DeepDermApplication {
    public static void main(String[] args) {
        SpringApplication.run(DeepDermApplication.class, args);
    }
}
