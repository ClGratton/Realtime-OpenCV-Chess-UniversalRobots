//buzzer function
void buzzer() {
  if (states == white_move || states == black_move) {
    for (int i = 4; i <= 5; i++) {
      if (buttonValues[i] == LOW) {
        tone(buzzerPin, 1000); // Send a 1kHz tone to the buzzer
        delay(150);
        noTone(buzzerPin);
      }
    }
  }
}
