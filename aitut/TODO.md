# TODO - Remove Redis, keep refresh tokens (DB-based)

- [ ] Remove Redis dependencies from `pom.xml`
- [ ] Remove Redis config from `application.properties`
- [ ] Remove RedisConfig bean/config class
- [ ] Replace Redis-based `RefreshToken` + `RefreshRepo` with PostgreSQL JPA entity + repository
- [ ] Update `RefreshTokenService` to use JPA refresh token storage
- [ ] Update `AuthController` `/refreshtoken` endpoint to use new DB refresh token
- [ ] Remove Redis messaging from `ReminderService` (StringRedisTemplate usage)
- [ ] Fix compilation errors / imports
- [ ] Run `mvn test` (or at least `mvn -q test`) to verify build

