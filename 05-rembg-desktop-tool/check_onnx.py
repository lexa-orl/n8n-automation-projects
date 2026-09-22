import sys, os
print("python:", sys.executable)

# onnxruntime import and providers
try:
    import onnxruntime as ort
    print("onnxruntime", ort.__version__)
    try:
        print("providers", ort.get_available_providers())
    except Exception as e:
        print("providers error:", repr(e))
except Exception as e:
    print("onnxruntime import error:", repr(e))

# PATH search for cublas DLLs
paths = os.environ.get('PATH', '').split(os.pathsep)
found = [os.path.join(p, f) for p in paths for f in ('cublasLt64_12.dll','cublasLt64_13.dll') if os.path.exists(os.path.join(p, f))]
print('cublas found in PATH:', found[:20])

# Check common locations
cuda_root = r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA'
if os.path.isdir(cuda_root):
    try:
        print('CUDA folders:', os.listdir(cuda_root))
    except Exception as e:
        print('Error listing CUDA folder:', e)
else:
    print('CUDA folder not found at', cuda_root)

# Check System32 for cublas
for fn in ('cublasLt64_12.dll','cublasLt64_13.dll'):
    p = os.path.join(r'C:\Windows\System32', fn)
    print(p, os.path.exists(p))
