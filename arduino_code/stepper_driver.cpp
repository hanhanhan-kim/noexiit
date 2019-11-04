#include "stepper_driver.h"
#include "Arduino.h"

const int StepperDriver::Degree_Per_Rev = 360;

// Stepper Controller Defaults
// ------------------------------------------------------------------------------------------------

// Default hardware parameters
const int StepperDriver::Default_Board_Num = 0;
const int StepperDriver::Default_CS_Pin = 10;
const int StepperDriver::Default_Reset_Pin = 7;
const int StepperDriver::Default_Busy_Pin = 8;
const int StepperDriver::Default_Fullstep_Per_Rev = 200;  
const byte StepperDriver::Default_Step_Mode = STEP_FS_64;

// Default current and kval parameters
const byte StepperDriver::Default_Kval_Acceleration = 40;
const byte StepperDriver::Default_Kval_Deceleration = 40;
const byte StepperDriver::Default_Kval_Run = 40;
const byte StepperDriver::Default_Kval_Hold = 20;
const String StepperDriver::Default_OC_Threshold = String("OC_3375mA");
//const String StepperDriver::Default_OC_Threshold = String("OC_2625mA");

// Default Movement parameters for jogging (deg/sec and deg/sec^2)
const float StepperDriver::Default_Jog_Speed = 400.0;
const float StepperDriver::Default_Jog_Acceleration = 800.0;
const float StepperDriver::Default_Jog_Deceleration = 800.0;

// Default Movement parameters max values (deg/sec and deg/sec^2)
const float StepperDriver::Default_Max_Speed = 4000.0;
const float StepperDriver::Default_Max_Acceleration = 80000.0;
const float StepperDriver::Default_Max_Deceleration = 80000.0;

// Micro to full step transistion (deg/sec)
const float StepperDriver::Default_Full_Speed = 2500.0;        


// Stepper controller methods
// ------------------------------------------------------------------------------------------------
StepperDriver::StepperDriver()
{
    enabled_ = false;

    set_board_num(Default_Board_Num);
    set_cs_pin(Default_CS_Pin); 
    set_reset_pin(Default_Reset_Pin);
    set_busy_pin(Default_Busy_Pin);
    set_fullstep_per_rev(Default_Fullstep_Per_Rev);

    set_jog_speed(Default_Jog_Speed);
    set_jog_acceleration(Default_Jog_Acceleration);
    set_jog_deceleration(Default_Jog_Acceleration);

    set_max_speed(Default_Max_Speed);
    set_max_acceleration(Default_Max_Acceleration);
    set_max_deceleration(Default_Max_Acceleration);

    // Temporary initialization ... don't call set methods because of SPI commands
    step_mode_ = Default_Step_Mode;  
}


StepperDriver::StepperDriver(int board_num, int cs_pin, int reset_pin, int busy_pin) : StepperDriver()
{
    set_board_num(board_num);
    set_cs_pin(cs_pin);
    set_reset_pin(reset_pin);
    set_busy_pin(busy_pin);
}


void StepperDriver::initialize()
{
    pinMode(cs_pin_,OUTPUT);
    pinMode(reset_pin_,OUTPUT);
    pinMode(busy_pin_,INPUT);

    pinMode(MOSI, OUTPUT);
    pinMode(MISO, INPUT);
    pinMode(SCK, OUTPUT);

    // Toggle reset pin
    digitalWrite(reset_pin_, HIGH);
    digitalWrite(reset_pin_, LOW);
    digitalWrite(reset_pin_, HIGH);
    // Initialize chip select
    digitalWrite(cs_pin_, HIGH);

    // Do we need this??
    delay(500);

    // Initialize SPI
    SPI.begin();
    SPI.setDataMode(SPI_MODE3);
    SPI.setBitOrder(MSBFIRST);

    // Initialize Driver 
    driver_ptr_ = new AutoDriver(board_num_,cs_pin_,reset_pin_,busy_pin_);  // ?? Should we be using the heap here???
    driver_ptr_->SPIPortConnect(&SPI);
    driver_ptr_->configSyncPin(BUSY_PIN,0);
    driver_ptr_->setOCShutdown(OC_SD_ENABLE);
    driver_ptr_->setSlewRate(SR_530V_us);
    driver_ptr_->resetDev();

    driver_ptr_->setFullSpeed(400.0);
    set_step_mode(Default_Step_Mode);
    set_movement_params_to_jog();

    set_acceleration_kval(Default_Kval_Acceleration);
    set_deceleration_kval(Default_Kval_Deceleration);
    set_run_kval(Default_Kval_Run);
    set_hold_kval(Default_Kval_Hold);
    set_oc_threshold(Default_OC_Threshold);

}


void StepperDriver::print_kval()
{
    byte acc_kval = driver_ptr_ -> getAccKVAL();
    byte dec_kval = driver_ptr_ -> getDecKVAL();
    byte run_kval = driver_ptr_ -> getRunKVAL();
    byte hld_kval = driver_ptr_ -> getHoldKVAL();

    Serial.print("acc_kval: " );
    Serial.println(acc_kval);
    Serial.print("dec_kval: " );
    Serial.println(dec_kval);
    Serial.print("run_kval: " );
    Serial.println(run_kval);
    Serial.print("hld_kval: " );
    Serial.println(hld_kval);
}

void StepperDriver::print_overcurrent_threshold()
{
    byte thresh = driver_ptr_ -> getOCThreshold();
    String thresh_string = get_string_from_oc_threshold(thresh);
    Serial.print("oc_thresh: ");
    Serial.println(thresh_string);

}

// Setters & getters for hardware parameters. 
// ------------------------------------------------------------------------------------------------
// Note, some of these board_num, cs_pin, reset_pin, & busy_pin must be set before initialization

void StepperDriver::set_board_num(int board_num)
{
    board_num_ = board_num;
}


int StepperDriver::get_board_num()   
{
    return board_num_;
}


void StepperDriver::set_cs_pin(int cs_pin)
{
    cs_pin_ = cs_pin;
}

int StepperDriver::get_cs_pin()      
{
    return cs_pin_;
}


void StepperDriver::set_reset_pin(int reset_pin)
{
    reset_pin_ = reset_pin;
}


int StepperDriver::get_reset_pin()   
{
    return reset_pin_;
}


void StepperDriver::set_busy_pin(int busy_pin)
{
    busy_pin_ = busy_pin;
}


int StepperDriver::get_busy_pin()    
{
    return busy_pin_;
}


void StepperDriver::set_fullstep_per_rev(int fullstep_per_rev)
{
    fullstep_per_rev_ = fullstep_per_rev;
    update_conversion_constants();
}



int StepperDriver::get_fullstep_per_rev()
{
    return fullstep_per_rev_;
}


bool StepperDriver::set_step_mode(byte step_mode)
{
    bool ok = false;
    if (step_mode == STEP_FS)
    {
        ok = true;
    }
    else if (step_mode == STEP_FS_2)
    {
        ok = true;
    }
    else if (step_mode == STEP_FS_4)
    {
        ok = true;
    }
    else if (step_mode == STEP_FS_8)
    {
        ok = true;
    }
    else if (step_mode == STEP_FS_16)
    {
        ok = true;
    }
    else if (step_mode == STEP_FS_32)
    {
        ok = true;
    }
    else if (step_mode == STEP_FS_64)
    {
        ok = true;
    }
    else if (step_mode == STEP_FS_128)
    {
        ok = true;
    }

    if (ok)
    {
        step_mode_ = step_mode;
        driver_ptr_-> configStepMode(step_mode_);
        update_conversion_constants();
    }
    return ok;
}


byte StepperDriver::get_step_mode()
{
    return driver_ptr_-> getStepMode();
}


bool StepperDriver::set_step_mode(String step_mode_string)
{
    byte step_mode;
    bool ok = get_step_mode_from_string(step_mode_string, step_mode);
    if (ok)
    {
        ok = set_step_mode(step_mode);
    }
    return ok;
}


String StepperDriver::get_step_mode_string()
{
    byte step_mode = get_step_mode();
    return get_string_from_step_mode(step_mode);
}


void StepperDriver::set_acceleration_kval(byte kval)
{
    driver_ptr_ -> setAccKVAL(kval);
}


byte StepperDriver::get_acceleration_kval()
{
    return driver_ptr_ -> getAccKVAL();
}


void StepperDriver::set_deceleration_kval(byte kval)
{
    driver_ptr_ -> setDecKVAL(kval);
}


byte StepperDriver::get_deceleration_kval()
{
    return driver_ptr_ -> getDecKVAL();
}


void StepperDriver::set_run_kval(byte kval)
{
    driver_ptr_ -> setRunKVAL(kval);
}


byte StepperDriver::get_run_kval()
{
    return driver_ptr_ -> getRunKVAL();
}


void StepperDriver::set_hold_kval(byte kval)
{
    driver_ptr_ -> setHoldKVAL(kval);
}


byte StepperDriver::get_hold_kval()
{
    return driver_ptr_ -> getHoldKVAL();
}


bool StepperDriver::set_oc_threshold(String threshold_string)
{
    bool ok= false;
    byte threshold_byte = get_oc_threshold_from_string(threshold_string, ok);
    if (ok)
    {
        driver_ptr_ -> setOCThreshold(threshold_byte) ;
    }
    return ok; 
}


String StepperDriver::get_oc_threshold()
{
    byte threshold_byte = driver_ptr_ -> getOCThreshold();
    return get_string_from_oc_threshold(threshold_byte);
}



// Setters & getters for motion parameters
// ------------------------------------------------------------------------------------------------

void StepperDriver::set_jog_speed(float speed)
{
    jog_speed_ = speed;
}


float StepperDriver::get_jog_speed()
{
    return jog_speed_;
}


void StepperDriver::set_jog_acceleration(float acceleration)
{
    jog_acceleration_ = acceleration;
}


float StepperDriver::get_jog_acceleration()
{
    return jog_acceleration_;
}


void StepperDriver::set_jog_deceleration(float deceleration)
{
    jog_deceleration_ = deceleration;
}


float StepperDriver::get_jog_deceleration()
{
    return jog_deceleration_;
}


void StepperDriver::set_max_speed(float speed)
{
    max_speed_ = speed;
}


float StepperDriver::get_max_speed()
{
    return max_speed_;
}


void StepperDriver::set_max_acceleration(float acceleration)
{
    max_acceleration_ = acceleration;
}


float StepperDriver::get_max_acceleration()
{
    return max_acceleration_;
}


void StepperDriver::set_max_deceleration(float deceleration)
{
    max_deceleration_ = deceleration;
}


float StepperDriver::get_max_deceleration()
{
    return max_deceleration_;
}


// Movement methods
// ------------------------------------------------------------------------------------------------

void StepperDriver::set_movement_params_to_jog()
{
    driver_ptr_->setMaxSpeed(degree_to_fullstep(jog_speed_));
    driver_ptr_->setAcc(degree_to_fullstep(jog_acceleration_));
    driver_ptr_->setDec(degree_to_fullstep(jog_deceleration_));
}


void StepperDriver::set_movement_params_to_max()
{
    driver_ptr_->setMaxSpeed(degree_to_fullstep(max_speed_));
    driver_ptr_->setAcc(degree_to_fullstep(max_acceleration_));
    driver_ptr_->setDec(degree_to_fullstep(max_deceleration_));
}


void StepperDriver::move_to(float pos)
{
    long pos_microstep = long(degree_to_microstep(pos));
    driver_ptr_-> goTo(pos_microstep);
    enabled_ = true;
}


void StepperDriver::move_to_fullsteps(float pos)
{
    driver_ptr_ -> goTo(long(pos*microstep_per_fullstep(step_mode_)));
    enabled_ = true;
}

void StepperDriver::move_to_microsteps(long pos)
{
    driver_ptr_ -> goTo(pos);
    enabled_ = true;
}


void StepperDriver::move_to_zero()
{
    move_to(0.0);
}


void StepperDriver::run(float velocity)
{
    byte direction = (velocity >= 0) ? FWD : REV;
    float speed = abs(velocity);
    driver_ptr_->run(direction,degree_to_fullstep(speed));
    enabled_ = true;
}


void StepperDriver::run_fullsteps(float velocity)
{
    byte direction = (velocity >= 0) ? FWD : REV;
    float speed = abs(velocity);
    driver_ptr_->run(direction,speed);
}


void StepperDriver::run_microsteps(float velocity)
{
    byte direction = (velocity >= 0) ? FWD : REV;
    float speed = abs(velocity)/microstep_per_fullstep(step_mode_);
    driver_ptr_->run(direction,speed);
}


bool StepperDriver::is_busy()
{
    return bool(driver_ptr_->busyCheck());
}


void StepperDriver::busy_wait()
{
    while (is_busy()) {};
}


float StepperDriver::get_position()
{
    return microstep_to_degree(driver_ptr_ -> getPos());
}


void StepperDriver::set_position(float pos)
{
    long pos_microstep = long(degree_to_microstep(pos));
    driver_ptr_ -> setPos(pos_microstep);
}


float StepperDriver::get_position_fullsteps()
{
    long pos_microstep = driver_ptr_ -> getPos();
    return  float(pos_microstep)/microstep_per_fullstep(step_mode_);
}


long StepperDriver::get_position_microsteps()
{
    return driver_ptr_ -> getPos();
}


void StepperDriver::soft_stop()
{
    driver_ptr_ -> softStop();
}


void StepperDriver::hard_stop()
{
    driver_ptr_ -> hardStop();
}


void StepperDriver::release()
{
    driver_ptr_ -> softHiZ();
    enabled_ = false;
}


void StepperDriver::enable()
{
    float pos = get_position();
    move_to(pos);
}

bool StepperDriver::is_enabled()
{
    return enabled_;
}




// ------------------------------------------------------------------------------------------------
// Protected Methods
// ------------------------------------------------------------------------------------------------


int StepperDriver::microstep_per_fullstep(byte step_mode)
{
    return int(1 << step_mode);
}


float StepperDriver::degree_to_fullstep(float value_degree)
{
    return fullstep_per_degree_*value_degree;
}


float StepperDriver::degree_to_microstep(float value_degree)
{
    return microstep_per_degree_*value_degree;
}


float StepperDriver::fullstep_to_degree(float value_fullstep)
{
    return degree_per_fullstep_*value_fullstep;
}


float StepperDriver::microstep_to_degree(float value_microstep)
{
    return degree_per_microstep_*value_microstep;
}

void StepperDriver::update_conversion_constants()
{
    fullstep_per_degree_ = float(fullstep_per_rev_)/float(Degree_Per_Rev);
    microstep_per_degree_ = fullstep_per_degree_*microstep_per_fullstep(step_mode_);;

    degree_per_fullstep_ = 1.0/fullstep_per_degree_;
    degree_per_microstep_ = 1.0/microstep_per_degree_;
}


void StepperDriver::reset()
{
    driver_ptr_ -> resetDev();
}




// Utility functions
// ------------------------------------------------------------------------------------------------
bool get_step_mode_from_string(String step_mode_string, byte &step_mode)
{
    bool success = true; 
    if (step_mode_string.equals("STEP_FS")) 
    {
        step_mode = STEP_FS;
    }
    else if (step_mode_string.equals("STEP_FS_2")) 
    {
        step_mode = STEP_FS_2;
    }
    else if (step_mode_string.equals("STEP_FS_4")) 
    {
        step_mode = STEP_FS_4;
    }
    else if (step_mode_string.equals("STEP_FS_8")) 
    {
        step_mode = STEP_FS_8;
    }
    else if (step_mode_string.equals("STEP_FS_16")) 
    {
        step_mode = STEP_FS_16;
    }
    else if (step_mode_string.equals("STEP_FS_32")) 
    {
        step_mode = STEP_FS_32;
    }
    else if (step_mode_string.equals("STEP_FS_64")) 
    {
        step_mode = STEP_FS_64;
    }
    else if (step_mode_string.equals("STEP_FS_128"))
    {
        step_mode = STEP_FS_128;
    }
    else
    {
        success = false;
    }
    return success;
}

String get_string_from_step_mode(byte step_mode)
{
    String step_mode_string;
    switch(step_mode)
    {
        case STEP_FS:   
            step_mode_string = String("STEP_FS");
            break;

        case STEP_FS_2:
            step_mode_string = String("STEP_FS_2");
            break;
                
        case STEP_FS_4:
            step_mode_string = String("STEP_FS_4");
            break;
                
        case STEP_FS_8:
            step_mode_string = String("STEP_FS_8");
            break;
                
        case STEP_FS_16:
            step_mode_string = String("STEP_FS_16");
            break;
             
        case STEP_FS_32:
            step_mode_string = String("STEP_FS_32");
            break;
             
        case STEP_FS_64:
            step_mode_string = String("STEP_FS_64");
            break;
             
        case STEP_FS_128:
            step_mode_string = String("STEP_FS_128");
            break;

        default:
            step_mode_string = String("NOT FOUND");
            break;
    }
    return step_mode_string;
}


String get_string_from_oc_threshold(byte thresh)
{
    String thresh_string;

    switch (thresh)
    {
        case OC_375mA:
            thresh_string = String("OC_375mA");
            break;

        case OC_750mA:  
            thresh_string = String("OC_750mA");
            break;

        case OC_1125mA: 
            thresh_string = String("OC_1125mA");
            break;

        case OC_1500mA: 
            thresh_string = String("OC_1500mA");
            break;

        case OC_1875mA: 
            thresh_string = String("OC_1875mA");
            break;

        case OC_2250mA: 
            thresh_string = String("OC_2250mA");
            break;

        case OC_2625mA: 
            thresh_string = String("OC_2625mA");
            break;

        case OC_3000mA: 
            thresh_string = String("OC_3000mA");
            break;

        case OC_3375mA: 
            thresh_string = String("OC_3375mA");
            break;

        case OC_3750mA: 
            thresh_string = String("OC_3750mA");
            break;

        case OC_4125mA: 
            thresh_string = String("OC_4125mA");
            break;

        case OC_4500mA: 
            thresh_string = String("OC_4500mA");
            break;

        case OC_4875mA: 
            thresh_string = String("OC_4875mA");
            break;

        case OC_5250mA: 
            thresh_string = String("OC_5250mA");
            break;

        case OC_5625mA: 
            thresh_string = String("OC_5625mA");
            break;

        case OC_6000mA: 
            thresh_string = String("OC_6000mA");
            break;

        default:
            thresh_string = String("NOT FOUND");
            break;

    }

    return thresh_string;
}


byte get_oc_threshold_from_string(String thresh_string, bool &found)
{
    byte thresh  = 0;

    found = true;

    if (thresh_string.equals("OC_375mA"))
    {
        thresh = OC_375mA;
    }
    else if (thresh_string.equals("OC_750mA"))
    {
        thresh = OC_750mA;
    }
    else if (thresh_string.equals("OC_1125mA"))
    {
        thresh = OC_1125mA;
    }
    else if (thresh_string.equals("OC_1500mA"))
    {
        thresh = OC_1500mA;
    }
    else if (thresh_string.equals("OC_1875mA"))
    {
        thresh = OC_1875mA;
    }
    else if (thresh_string.equals("OC_2250mA"))
    {
        thresh = OC_2250mA;
    }
    else if (thresh_string.equals("OC_2625mA"))
    {
        thresh = OC_2625mA;
    }
    else if (thresh_string.equals("OC_3000mA"))
    {
        thresh = OC_3000mA;
    }
    else if (thresh_string.equals("OC_3375mA"))
    {
        thresh = OC_3375mA;
    }
    else if (thresh_string.equals("OC_3750mA"))
    {
        thresh = OC_3750mA;
    }
    else if (thresh_string.equals("OC_4125mA"))
    {
        thresh = OC_4125mA;
    }
    else if (thresh_string.equals("OC_4500mA"))
    {
        thresh = OC_4500mA;
    }
    else if (thresh_string.equals("OC_4875mA"))
    {
        thresh = OC_4875mA;
    }
    else if (thresh_string.equals("OC_5250mA"))
    {
        thresh = OC_5250mA;
    }
    else if (thresh_string.equals("OC_5625mA"))
    {
        thresh = OC_5625mA;
    }
    else if (thresh_string.equals("OC_6000mA"))
    {
        thresh = OC_6000mA;
    }
    else
    {
        found = false;
    }
    return thresh;
}


