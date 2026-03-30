package com.example.demo.repository;

import com.example.demo.model.RefreshToken;
import org.springframework.data.repository.CrudRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;

@Repository
public interface RefreshRepo extends CrudRepository<RefreshToken, String> {
    // Because we added @Indexed to username, we can do this:
    Optional<RefreshToken> findByUsername(String username);
}
