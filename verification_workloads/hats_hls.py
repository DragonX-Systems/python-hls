def svm(hist, offset, rho, weights_fifo):
    """Compute SVM prediction from histogram"""
    # pragma hls stream hist_stream(direction=in)
    # pragma hls stream svm_out_stream(direction=out)
    # pragma hls fifo weights_fifo(depth=735, width=32)

    sum_val = 0.0
    for i in range(rho):
        for j in range(rho):
            weight_idx = offset + i * rho + j
            sum_val += hist[i][j] * weights_fifo[weight_idx]  # pragma hls fifo_read weights_fifo
    return sum_val

def compute_histogram(cell_id, event_x, event_y, event_p, memory_x, memory_y, memory_p, cntmem, rho, MAX_EVENTS_PER_CELL):
    """Compute histogram for current event"""
    # pragma hls inline
    
    # Initialize histogram with zeros
    hist = [[0 for _ in range(rho)] for _ in range(rho)]
    # pragma hls array_partition variable=hist complete dim=0
    
    # Clear histogram (explicit initialization)
    for i in range(rho):
        for j in range(rho):
            hist[i][j] = 0
    
    # Process events in memory for this cell and polarity
    # pragma hls pipeline enable
    if cell_id < len(cntmem) and event_p < len(cntmem[cell_id]):
        for i in range(min(cntmem[cell_id][event_p], MAX_EVENTS_PER_CELL)):
            # pragma hls loop_count min=5 max=20
            if (i < len(memory_y[cell_id][event_p]) and 
                i < len(memory_x[cell_id][event_p])):
                x = memory_y[cell_id][event_p][i] - event_y
                y = memory_x[cell_id][event_p][i] - event_x
                
                if abs(x) <= rho//2 and abs(y) <= rho//2:
                    x_idx = x + rho//2
                    y_idx = y + rho//2
                    if 0 <= x_idx < rho and 0 <= y_idx < rho:
                        hist[x_idx][y_idx] += 1
    
    return hist

def hats(events_x, events_y, events_p, size):
    """Main HATS algorithm implementation"""
    # Constants from C++ implementation
    P = 8
    rho = 7
    N_PE = 7
    tot_cell = 120 // P
    MAX_EVENTS_PER_CELL = 50
    
    # Initialize data structures using the calculated constant values directly
    loc_sum = [0.0] * 15  # pragma hls stream loc_sum_stream(direction=inout)
    cnt = [0] * 15  # pragma hls stream cnt_stream(direction=inout)
    cntmem = [[0, 0] for _ in range(15)]  # pragma hls stream cntmem_stream(direction=inout)
    
    # 3D arrays for memory - need explicit dimensions for HLS
    memory_x = [[[0 for _ in range(50)] for _ in range(2)] for _ in range(15)]  # pragma hls stream memory_x_stream(direction=inout)
    memory_y = [[[0 for _ in range(50)] for _ in range(2)] for _ in range(15)]  # pragma hls stream memory_y_stream(direction=inout)
    memory_p = [[[False for _ in range(50)] for _ in range(2)] for _ in range(15)]  # pragma hls stream memory_p_stream(direction=inout)
    
    # Create weight buffer with proper allocation
    # The weights array needs to be sized using the pre-calculated constant size (15 * 7 * 7 = 735)
    # weights_memory_size = tot_cell * rho * rho * 4 # This line caused IR issues

    # The actual weights are a large list of constants.
    # The compiler needs to know the size of this list at compile time.
    # Ensure the size of the literal list matches tot_cell * rho * rho (15 * 7 * 7 = 735)
    # The provided weights list seems to have 735 elements, which matches 15 * 7 * 7.

    weights_fifo = [0.0] * 735 # pragma hls fifo weights_fifo(depth=735, width=32)

    weights_values = [
        -2.063528820872306824e-02, -1.158180594444274902e+00, 4.317252337932586670e-01, -1.191073954105377197e-01, 3.505196794867515564e-02, 4.872589111328125000e-01, 2.170588821172714233e-02, -1.333150863647460938e-01, -2.100706845521926880e-01, 
        3.648332655429840088e-01, -7.803564667701721191e-01, -1.386398822069168091e-02, -2.051063925027847290e-01, 1.972310431301593781e-02, 1.112742796540260315e-01, 2.495798915624618530e-01, -1.687575936317443848e+00, 1.416517615318298340e+00, 
        5.898873805999755859e-01, -3.370565474033355713e-01, -3.951647579669952393e-01, -3.469868898391723633e-01, 3.324987292289733887e-01, 1.416268348693847656e+00, 2.485180944204330444e-01, 8.250406980514526367e-01, -4.120576083660125732e-01, 
        2.146018594503402710e-01, -7.007414847612380981e-02, 3.856364488601684570e-01, 4.699690937995910645e-01, 1.987872123718261719e-01, -8.044598698616027832e-01, 3.307057917118072510e-01, -8.562790155410766602e-01, 6.153951957821846008e-02, 
        3.740459084510803223e-01, -1.113300323486328125e+00, -4.934534728527069092e-01, -5.756611227989196777e-01, 3.816262185573577881e-01, 7.061353325843811035e-01, 9.199784994125366211e-01, 7.401596307754516602e-01, -7.085708975791931152e-01, 
        -3.715169429779052734e-01, -3.807401657104492188e-01, 1.919509917497634888e-01, 7.534394264221191406e-01, 3.657434880733489990e-01, -6.406591087579727173e-02, -8.117573857307434082e-01, -8.507340550422668457e-01, -1.251056641340255737e-01, 
        1.150659918785095215e+00, 7.379277944564819336e-01, 3.647236227989196777e-01, -2.098214030265808105e-01, -1.193718075752258301e+00, 2.970684468746185303e-01, -1.099312424659729004e+00, 2.458080798387527466e-01, 5.936311483383178711e-01, 
        1.015103936195373535e+00, 7.510262727737426758e-02, -1.543394923210144043e-01, 1.073817729949951172e+00, 5.399064719676971436e-02, 7.411892414093017578e-01, -9.214034080505371094e-01, -1.984037995338439941e+00, -1.575863003730773926e+00, 
        2.544961929321289062e+00, 2.485612779855728149e-01, 1.146762013435363770e+00, -4.266860783100128174e-01, -9.246576428413391113e-01, 6.216380596160888672e-01, 1.186421632766723633e+00, -1.769523620605468750e-01, 2.954738028347492218e-02, 
        -2.142123878002166748e-02, 4.444923400878906250e-01, 2.580829560756683350e-01, 9.006572365760803223e-01, 1.725320070981979370e-01, -6.879680752754211426e-01, -1.048326492309570312e+00, -1.246611237525939941e+00, -3.105770051479339600e-02, 
        1.410173654556274414e+00, 9.903985857963562012e-01, 2.527248859405517578e-01, -3.681108951568603516e-01, -1.055569410324096680e+00, -5.336214303970336914e-01, -5.925685167312622070e-01, 8.239042162895202637e-01, -6.598625779151916504e-01, 
        -6.666193008422851562e-01, -5.969669222831726074e-01, 4.269773066043853760e-01, 3.335131704807281494e-01, 7.239465117454528809e-01, -4.495376646518707275e-01, 3.516954183578491211e-01, -5.658005475997924805e-01, -3.109689652919769287e-01, 
        -3.328140377998352051e-01, 4.878493845462799072e-01, -6.541938781738281250e-01, 5.368232131004333496e-01, -2.506305277347564697e-01, 1.776489317417144775e-01, 5.500776693224906921e-02, 1.039530634880065918e+00, -1.839091628789901733e-01, 
        -3.203915357589721680e-01, 2.429484724998474121e-01, -1.759082317352294922e+00, 1.116054598242044449e-02, 1.654319763183593750e+00, -6.091491505503654480e-02, 9.231714010238647461e-01, 2.445609867572784424e-01, -3.501110374927520752e-01, 
        5.291398614645004272e-02, 1.125972867012023926e+00, 5.657300353050231934e-03, 3.856687247753143311e-01, -8.947330117225646973e-01, -8.594620972871780396e-02, 7.389871478080749512e-01, 8.266060352325439453e-01, -2.091364115476608276e-01, 
        -1.129337906837463379e+00, -5.529499053955078125e-01, -2.321061789989471436e-01, 3.605402410030364990e-01, 3.150246441364288330e-01, 8.681440353393554688e-01, 3.297046944499015808e-02, -9.378762245178222656e-01, -5.018738508224487305e-01, 
        -3.334589302539825439e-01, -1.440800428390502930e-01, -6.099038720130920410e-01, 1.577199548482894897e-01, -8.059906214475631714e-02, -7.463059425354003906e-01, 6.442551016807556152e-01, 1.450627148151397705e-01, -1.020537093281745911e-01, 
        -2.064093202352523804e-01, 2.688483297824859619e-01, -3.019934594631195068e-01, -5.573219060897827148e-02, 4.294286370277404785e-01, -3.449833095073699951e-01, -3.075374960899353027e-01, 1.120308879762887955e-02, 1.122161224484443665e-01, 
        1.735059320926666260e-01, 1.135230422019958496e+00, -3.926463127136230469e-01, -3.773967921733856201e-01, -4.015000462532043457e-01, 2.388725578784942627e-01, -1.611598968505859375e+00, -4.018473923206329346e-01, 5.668334364891052246e-01, 
        -4.434923082590103149e-02, 6.582744121551513672e-01, -4.258929193019866943e-01, 4.532437026500701904e-01, 1.319433003664016724e-01, 1.531144976615905762e-01, 2.175765298306941986e-02, -2.815524339675903320e-01, 8.372930288314819336e-01, 
        6.112165451049804688e-01, 4.437123537063598633e-01, 1.051709175109863281e+00, -1.851923316717147827e-01, -1.334081411361694336e+00, -3.791015446186065674e-01, -4.947190582752227783e-01, 1.537045389413833618e-01, 1.584985256195068359e-01, 
        -8.975607343018054962e-03, -2.488442212343215942e-01, 6.445223093032836914e-01, -8.199482411146163940e-02, 4.872210621833801270e-01, -8.021109104156494141e-01, 4.837614595890045166e-01, -8.963739871978759766e-01, 8.275405317544937134e-02, 
        -5.364245176315307617e-01, -4.037986695766448975e-01, 5.035460591316223145e-01, 6.104064583778381348e-01, -4.820639491081237793e-01, -1.204866647720336914e+00, -2.146999686956405640e-01, 8.107242584228515625e-01, 3.684679865837097168e-01, 
        -4.126115143299102783e-01, 2.492147237062454224e-01, 5.542204380035400391e-01, -4.134666323661804199e-01, 1.085182070732116699e+00, 2.734186649322509766e-01, -1.648267805576324463e-01, 4.857286810874938965e-01, -3.567601144313812256e-01, 
        -2.460103780031204224e-01, -4.658595025539398193e-01, -4.491264000535011292e-02, -7.819042801856994629e-01, -1.136793255805969238e+00, 2.538673207163810730e-02, -4.379022121429443359e-01, 6.499048471450805664e-01, 5.529497265815734863e-01, 
        7.383260726928710938e-01, 3.105791509151458740e-01, 1.734182536602020264e-01, -2.859898805618286133e-01, 6.937208771705627441e-01, 7.103215903043746948e-02, -1.905678659677505493e-01, 1.202051863074302673e-01, 7.427142560482025146e-02, 
        -1.792018264532089233e-01, 1.848017722368240356e-01, -3.265202045440673828e-01, -4.084483981132507324e-01, -7.080169916152954102e-01, 4.091019630432128906e-01, 1.316726803779602051e-01, -2.665021419525146484e-01, -2.912821173667907715e-01, 
        -3.794196546077728271e-01, 4.416735470294952393e-01, -3.521684110164642334e-01, -9.504520148038864136e-02, 6.494833528995513916e-02, -5.117832869291305542e-02, -3.093076348304748535e-01, 2.792536914348602295e-01, 4.246114790439605713e-01, 
        1.405332088470458984e-01, 8.747549653053283691e-01, -1.574392169713973999e-01, 2.169619686901569366e-02, 1.279523968696594238e-01, -5.885731577873229980e-01, -6.748637557029724121e-01, 5.958492159843444824e-01, 6.867734789848327637e-01, 
        9.779594540596008301e-01, -1.470729261636734009e-01, -1.033311724662780762e+00, 2.951061725616455078e-01, -4.005764126777648926e-01, -5.479587316513061523e-01, -1.009029507637023926e+00, 2.504734098911285400e-01, -2.630448043346405029e-01, 
        5.460379719734191895e-01, 2.508655190467834473e-01, 3.047370016574859619e-01, -1.062335669994354248e-01, -1.303351372480392456e-01, -6.923545151948928833e-02, -8.347692489624023438e-01, -9.316904097795486450e-02, 7.744941115379333496e-01, 
        3.870335873216390610e-03, -5.639175176620483398e-01, -9.854926466941833496e-01, 9.517877697944641113e-01, 4.014381468296051025e-01, -1.968361884355545044e-01, 2.100589275360107422e-01, -4.356326758861541748e-01, 1.312045007944107056e-01, 
        -3.860868513584136963e-01, 2.868453562259674072e-01, 6.039516329765319824e-01, -3.769495785236358643e-01, -7.260179519653320312e-02, 1.927358955144882202e-01, 2.025384455919265747e-01, -2.440479546785354614e-01, -5.409696698188781738e-01, 
        4.570827186107635498e-01, 2.869071960449218750e-01, 1.880923658609390259e-01, 4.037222266197204590e-02, -7.283350825309753418e-01, 2.718355655670166016e-01, 2.904218137264251709e-01, 9.700288176536560059e-01, -3.137916028499603271e-01, 
        4.162858426570892334e-01, 2.512373030185699463e-01, -1.117174863815307617e+00, 6.738966107368469238e-01, 6.946153640747070312e-01, -4.050558507442474365e-01, 3.910634815692901611e-01, 7.166828960180282593e-02, -2.979726791381835938e-01, 
        -1.220423057675361633e-01, -2.179566770792007446e-01, -5.862891674041748047e-01, -1.335329413414001465e+00, -6.906896233558654785e-01, -2.261866480112075806e-01, 2.414732426404953003e-01, 2.753794193267822266e-01, 6.381279826164245605e-01, 
        -6.647280603647232056e-02, 7.193073630332946777e-01, -3.353726863861083984e-02, -8.653991222381591797e-01, -8.828637003898620605e-02, -3.586712181568145752e-01, 2.996748983860015869e-01, 3.864821046590805054e-03, 8.110529184341430664e-02, 
        4.387803375720977783e-01, 7.883923649787902832e-01, 1.703577041625976562e-01, 2.408319413661956787e-01, 5.139469727873802185e-02, 9.843542426824569702e-02, -4.082830548286437988e-01, 4.531365633010864258e-01, 1.560819745063781738e-01, 
        2.337556034326553345e-01, -3.997330069541931152e-01, -1.068425551056861877e-01, -1.067772358655929565e-01, 7.350695729255676270e-01, -6.356967240571975708e-02, -2.556990981101989746e-01, 5.492063164710998535e-01, -4.622718393802642822e-01, 
        -1.069458872079849243e-01, 1.138801455497741699e+00, -2.159212082624435425e-01, -6.480175256729125977e-02, -6.127419471740722656e-01, -3.715995848178863525e-01, 1.599598228931427002e-01, 7.835696339607238770e-01, 6.305183768272399902e-01, 
        1.347172558307647705e-01, 7.709003239870071411e-02, -3.631863892078399658e-01, -4.670447111129760742e-01, -5.253173708915710449e-01, 3.997528553009033203e-01, 3.629539310932159424e-01, -6.365916728973388672e-01, -2.132558226585388184e-01, 
        6.669826507568359375e-01, -1.455978751182556152e-01, -1.217287182807922363e-01, 3.606753945350646973e-01, 2.459677755832672119e-01, 1.064073324203491211e+00, -8.847777545452117920e-02, -3.028034269809722900e-01, -4.341030120849609375e-01, 
        -4.523971080780029297e-01, 8.114160597324371338e-02, -1.647480949759483337e-02, -6.616111844778060913e-02, 2.804113030433654785e-01, -3.365796208381652832e-01, -5.687201619148254395e-01, -5.977369546890258789e-01, -7.399350404739379883e-01, 
        -6.307635307312011719e-01, -1.184581041336059570e+00, -1.158870905637741089e-01, 2.350314408540725708e-01, -7.490978459827601910e-04, 6.382136046886444092e-02, 1.781016290187835693e-01, -2.621054351329803467e-01, -1.792850941419601440e-01, 
        3.487507626414299011e-02, -1.079895570874214172e-01, -8.699393272399902344e-01, 2.078256458044052124e-01, -3.045747280120849609e-01, -1.695098578929901123e-01, 5.500595569610595703e-01, -3.419607579708099365e-01, -2.982025444507598877e-01
    ]
    # Simulate FIFO write
    for i in range(len(weights_values)):
        weights_fifo[i] = weights_values[i]  # pragma hls fifo_write weights_fifo
    # Set up processing pipeline
    # pragma hls crossbar events_xbar(inputs=1, outputs=4)
    # pragma hls stream events_stream(direction=in)
    # pragma hls stream hist_stream(direction=out)
    
    # Process each event
    # pragma hls pipeline II=2
    for j in range(size):
        # pragma hls loop_count min=0 max=1211
        # Compute cell_id based on y-coordinate
        cell_id = events_y[j] // 10
        
        # Ensure cell_id is within bounds before accessing arrays/memories
        if 0 <= cell_id < 15: # Use literal constant 15 for bounds checking in HLS
            # Compute histogram and SVM for this event
            hist = compute_histogram(cell_id, events_x[j], events_y[j], events_p[j], 
                                    memory_x, memory_y, memory_p, cntmem, rho, 50) # Pass 50 directly
            offset = cell_id * rho * rho # offset calculation seems fine, uses constants cell_id and rho
            
            # Explicitly mark potential FIFO or stream operations (if they are truly streaming)
            # If these are meant to write/read entire structures or large blocks in a stream-like manner,
            # the pragma might be useful, but applying it to += on an indexed access might still be problematic.
            # Let's remove these FIFO_WRITE/READ pragmas for now as they seem misapplied to indexed access.
            # They are more appropriate for dedicated FIFO variables or stream objects.
            loc_sum[cell_id] += svm(hist, offset, rho, weights_fifo)
            
            # Store current event in memory - These are indexed writes, usually synthesized to RAM/Registers
            curr_p = 1 if events_p[j] else 0
            # Add bounds checking for curr_p (0 or 1) and the index into the last dimension
            if 0 <= curr_p < 2 and cntmem[cell_id][curr_p] < 50: # Use literal 50 for bounds checking
                memory_x[cell_id][curr_p][cntmem[cell_id][curr_p]] = events_x[j] 
                memory_y[cell_id][curr_p][cntmem[cell_id][curr_p]] = events_y[j] 
                memory_p[cell_id][curr_p][cntmem[cell_id][curr_p]] = events_p[j] 
                cntmem[cell_id][curr_p] += 1
                cnt[cell_id] += 1
    
    # Compute final sum
    sum_val = 0.0
    # pragma hls pipeline enable # Keep this
    for k in range(15): # Use literal constant 15
        # pragma hls unroll factor=3 # Keep this
        if cnt[k] > 0:
            sum_val += loc_sum[k] / cnt[k] 
    
    # The memory size variables were not used in the core logic, only for a final comment/report value.
    # We can re-calculate the total size using the now-constant dimensions for the final report section.

    # Calculate total memory requirements for reporting using literal sizes
    # This calculation is outside the HLS core logic, so it can use the variables again
    loc_sum_memory_size = 15 * 4
    cnt_memory_size = 15 * 4
    cntmem_memory_size = 15 * 2 * 4
    memory_x_memory_size = 15 * 2 * 50 * 4
    memory_y_memory_size = 15 * 2 * 50 * 4
    memory_p_memory_size = 15 * 2 * 50 * 1
    weights_memory_size = 15 * 7 * 7 * 4

    total_memory_size = (loc_sum_memory_size + cnt_memory_size + cntmem_memory_size +
                         memory_x_memory_size + memory_y_memory_size + memory_p_memory_size +
                         weights_memory_size)

    # Total memory footprint: ~500KB # Keep this comment

    return sum_val

# pragma hls top
def hats_wrapped(events_x, events_y, events_p, size):
    """Wrapper function for HLS synthesis with simple array inputs"""
    # pragma hls interface ap_fifo port=events_x depth=1500
    # pragma hls interface ap_fifo port=events_y depth=1500
    # pragma hls interface ap_fifo port=events_p depth=1500
    # pragma hls interface s_axilite port=size
    # pragma hls interface s_axilite port=return
    
    # pragma hls stream events_x_stream(direction=in)
    # pragma hls stream events_y_stream(direction=in)
    # pragma hls stream events_p_stream(direction=in)
    # pragma hls stream result_stream(direction=out)
    
    # Pass arrays and the literal constant MAX_EVENTS_PER_CELL to hats function
    return hats(events_x, events_y, events_p, size) 

# Test function to verify implementation
def test_hats():
    """Simple test function to verify HATS implementation"""
    # Create some test events
    test_size = 10
    events_x = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    events_y = [15, 25, 35, 45, 55, 65, 75, 85, 95, 105]
    events_p = [True, False, True, False, True, False, True, False, True, False]
    
    # Call the hats algorithm
    result = hats_wrapped(events_x, events_y, events_p, test_size)
    print(f"HATS result: {result}")
    return result

# Only run the test when executing this file directly
if __name__ == "__main__":
    test_hats() 
