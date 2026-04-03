import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

public class TestBCrypt {
    public static void main(String[] args) {
        BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
        String hash = "$2a$12$vE5y7RlD/Mok6ZkHgGUGMuFE.bJ2NzFQM6G9Gl6ZGNz1PVSOkjdpO";
        System.out.println("password: " + encoder.matches("password", hash));
        System.out.println("password123: " + encoder.matches("password123", hash));
        System.out.println("DeepDerm2024!: " + encoder.matches("DeepDerm2024!", hash));
    }
}
