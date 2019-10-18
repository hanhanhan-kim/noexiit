// Set the current limit to 2400 mA.
// Documentation: http://pololu.github.io/high-power-stepper-driver

// SET-UP -----------------------------------------------------------------------

#include <Servo.h>
#include <SPI.h>
#include <HighPowerStepperDriver.h>

// Comment this line to exclude prints, making things a little faster
// (though, idk, maybe not to an extent that matters, or maybe not enough.
// fuck.)
//#define PRINT_STUFF

// Servo pin:
const uint8_t servo_pin = 9;
// Stepper pins:
const uint8_t dir_pin = 2;
const uint8_t step_pin = 3;
const uint8_t cs_pin = 4;

// Initialize my servo as a servo:
Servo servo;
// Initialize my stepper as a high-powered stepper:
HighPowerStepperDriver sd;

// Initialize my servo pos as position 0;
int pos = 0;

// This period is the length of the delay between steps, which controls the
// stepper motor's speed.  You can increase the delay to make the stepper motor
// go slower.  If you decrease the delay, the stepper motor will go faster, but
// there is a limit to how fast it can go before it starts missing steps.
const uint16_t StepPeriodUs = 100;
// Define the microstepping size (not the reciprocal, e.g. not 1/32, but 32)
int microstepping = 32;

// FUNCTIONS -----------------------------------------------------------------------

float read_float() {
  union u_tag {
    byte b[4];
    float floatval;
  } u;

  while (Serial.available() < 4) { }

  u.b[0] = Serial.read();
  u.b[1] = Serial.read();
  u.b[2] = Serial.read();
  u.b[3] = Serial.read();

  return u.floatval;
}

// Sends a pulse on the STEP pin to tell the driver to take one step, and also
//delays to control the speed of the motor.
void step() {
  // The STEP minimum high pulse width is 1.9 microseconds.
  // (though the time digitalWrite takes may make the delayMicroseconds
  // unecessary)
  digitalWrite(step_pin, HIGH);
  delayMicroseconds(3);
  digitalWrite(step_pin, LOW);
  delayMicroseconds(3);
}

// Writes a high or low value to the direction pin to specify what direction to
// turn the motor.
void setDirection(bool dir) {
  // The STEP pin must not change for at least 200 nanoseconds before and after
  // changing the DIR pin.
  delayMicroseconds(1);
  digitalWrite(dir_pin, dir);
  delayMicroseconds(1);
}


void rotate(float deg_increm) {
  setDirection(deg_increm > 0);

  // fullstep is 0.9 deg, gear ratio is 2.4
  unsigned int step_increm = round(2.4 * abs(deg_increm) / 0.9 * microstepping);
  //unsigned int step_increm = 400 * microstepping;
  for (unsigned int i = 0; i <= step_increm; i++) {
    step();
    delayMicroseconds(StepPeriodUs);
  }
}

int servo_pos = 0;
void init_servo() {
  /*
    servo.write(servo_pos);
    delay(2700);
  */
  for (int pos = 180; pos > 0; pos--) {
    servo.write(pos);
    delay(15);
  }
}


void lineate(float mm_pos) {
  // Way we calculated this conversion factor:
  // 1) Found arguments to the servo.write fn (going through the loop below),
  // that did not make the servo behave weird. (40 and 150)
  // 2) (150 - 40) / (effective mm stroke given those arguments)
  // !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  // !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  // To make this accurate, we need to measure the denominator, if not crystal
  // clear what relationship between servo.write argument and position is from
  // docs.
  // !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  // !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  // 3) for now, we are estimating denominator to be 1cm
  int target_servo_pos = 40 + round(mm_pos * 9);

  if (target_servo_pos < 40) {
    target_servo_pos = 40;
  } else if (target_servo_pos > 150) {
    target_servo_pos = 150;
  }

  int servo_step;
  if (target_servo_pos >= servo_pos) {
    servo_step = 1;
  } else {
    servo_step = -1;
  }

  /*
  for (int pos = servo_pos; pos != target_servo_pos; pos += servo_step) {
    servo.write(pos);
    delay(15);
  }
  servo.write(target_servo_pos);
  delay(15);
  servo_pos = target_servo_pos;
  */
  servo.write(target_servo_pos);
}


void setup() {
  // Attach the servo to the servo pin.
  servo.attach(servo_pin);

  SPI.begin();
  sd.setChipSelectPin(cs_pin);

  // Initialize the STEP and DIR pins to low.
  pinMode(step_pin, OUTPUT);
  digitalWrite(step_pin, LOW);
  pinMode(dir_pin, OUTPUT);
  digitalWrite(dir_pin, LOW);

  // Give the driver 1 ms to power up.
  delay(1);

  // Reset the driver to its default settings and clear latched status conditions.
  sd.resetSettings();
  sd.clearStatus();

  // Select auto mixed decay.
  // TI's DRV8711 documentation recommends the auto mixed decay mode.
  sd.setDecayMode(HPSDDecayMode::AutoMixed);

  // Set the current limit.
  sd.setCurrentMilliamps36v4(2400);

  // Set the number of microsteps that corresponds to one full step.
  // sd.setStepMode(HPSDStepMode::MicroStep32);
  if (microstepping == 1) {
    sd.setStepMode(HPSDStepMode::MicroStep1);
  } else if (microstepping == 2) {
    sd.setStepMode(HPSDStepMode::MicroStep2);
  } else if (microstepping == 4) {
    sd.setStepMode(HPSDStepMode::MicroStep4);
  } else if (microstepping == 8) {
    sd.setStepMode(HPSDStepMode::MicroStep8);
  } else if (microstepping == 16) {
    sd.setStepMode(HPSDStepMode::MicroStep16);
  } else if (microstepping == 32) {
    sd.setStepMode(HPSDStepMode::MicroStep32);
  } else if (microstepping == 64) {
    sd.setStepMode(HPSDStepMode::MicroStep64);
  } else if (microstepping == 128) {
    sd.setStepMode(HPSDStepMode::MicroStep128);
  } else if (microstepping == 256) {
    sd.setStepMode(HPSDStepMode::MicroStep256);
  }

  // Enable the motor outputs.
  sd.enableDriver();

  Serial.begin(9600);

  // may need to uncomment for some bizarre reason
  //init_servo();
}

void loop() {
  #ifdef PRINT_STUFF
  Serial.println("reading linear actuator move position");
  #endif
  
  float curr_mm = read_float();
  
  #ifdef PRINT_STUFF
  Serial.println("reading stepper move amount");
  #endif
  
  float curr_deg_increm = read_float();
  
  #ifdef PRINT_STUFF
  Serial.println("moving linear actuator to:");
  Serial.println(curr_mm);
  #endif
  
  lineate(curr_mm);
  
  #ifdef PRINT_STUFF
  Serial.println("moving stepper motor by:");
  Serial.println(curr_deg_increm);
  #endif
  
  rotate(curr_deg_increm);
  Serial.println("ok");
}
