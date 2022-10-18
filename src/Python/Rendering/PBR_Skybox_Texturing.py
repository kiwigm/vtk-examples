#!/usr/bin/env python3

import json
import sys
from pathlib import Path

# noinspection PyUnresolvedReferences
import vtkmodules.vtkRenderingOpenGL2
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkCommonComputationalGeometry import (
    vtkParametricBoy,
    vtkParametricMobius,
    vtkParametricRandomHills,
    vtkParametricTorus
)
from vtkmodules.vtkCommonCore import (
    VTK_VERSION_NUMBER,
    vtkCommand,
    vtkFloatArray,
    vtkVersion
)
from vtkmodules.vtkCommonDataModel import vtkPlane
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersCore import (
    vtkCleanPolyData,
    vtkClipPolyData,
    vtkPolyDataNormals,
    vtkPolyDataTangents,
    vtkTriangleFilter
)
from vtkmodules.vtkFiltersGeneral import vtkTransformPolyDataFilter
from vtkmodules.vtkFiltersModeling import vtkLinearSubdivisionFilter
from vtkmodules.vtkFiltersSources import (
    vtkCubeSource,
    vtkParametricFunctionSource,
    vtkTexturedSphereSource
)
from vtkmodules.vtkIOImage import (
    vtkHDRReader,
    vtkJPEGWriter,
    vtkImageReader2Factory,
    vtkPNGWriter
)
from vtkmodules.vtkImagingCore import vtkImageFlip
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkInteractionWidgets import (
    vtkCameraOrientationWidget,
    vtkOrientationMarkerWidget,
    vtkSliderRepresentation2D,
    vtkSliderWidget
)
from vtkmodules.vtkRenderingAnnotation import vtkAxesActor
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkPolyDataMapper,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
    vtkSkybox,
    vtkTexture,
    vtkRenderer,
    vtkWindowToImageFilter
)
from vtkmodules.vtkRenderingOpenGL2 import (
    vtkCameraPass,
    vtkEquirectangularToCubeMapTexture,
    vtkLightsPass,
    vtkOpaquePass,
    vtkOpenGLRenderer,
    vtkOverlayPass,
    vtkRenderPassCollection,
    vtkSequencePass,
    vtkToneMappingPass
)


def get_program_parameters():
    import argparse
    description = 'Demonstrates physically based rendering, image based lighting, texturing and a skybox.'
    epilogue = '''
Physically based rendering sets color, metallicity and roughness of the object.
Image based lighting uses a cubemap texture to specify the environment.
Texturing is used to generate lighting effects.
A Skybox is used to create the illusion of distant three-dimensional surroundings.
    '''
    parser = argparse.ArgumentParser(description=description, epilog=epilogue,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('file_name', help='The path to the JSON file.')
    parser.add_argument('-s', '--surface', default='',
                        help='The name of the surface. Overrides the surface entry in the json file.')
    parser.add_argument('-c', '--use_cubemap', action='store_true',
                        help='Build the cubemap from the six cubemap files.'
                             ' Overrides the equirectangular entry in the json file.')
    args = parser.parse_args()
    return args.file_name, args.surface, args.use_cubemap


def main():
    if not vtk_version_ok(9, 0, 0):
        print('You need VTK version 9.0 or greater to run this program.')
        return

    fn, surface_name, use_cubemap = get_program_parameters()

    fn_path = Path(fn)
    if not fn_path.suffix:
        fn_path = fn_path.with_suffix(".json")
    if not fn_path.is_file():
        print('Unable to find: ', fn_path)
    paths_ok, parameters = get_parameters(fn_path, surface_name)
    if not paths_ok:
        return
    res = display_parameters(parameters)
    print('\n'.join(res))
    print()

    if not check_for_missing_textures(parameters, ['albedo', 'normal', 'material', 'emissive']):
        return

    # Choose how to generate the skybox.
    cube_map = None
    env_texture = None
    has_env_texture = False
    is_hdr = False
    has_cube_map = False
    gamma_correct = False
    if not parameters['skybox']:
        use_cubemap = False
    if use_cubemap and 'cubemap' in parameters.keys():
        print('Using the cubemap files to generate the environment texture.')
        cube_map = read_cubemap(parameters['cubemap'])
        has_cube_map = True
    elif 'equirectangular' in parameters.keys() and parameters['equirectangular']:
        print('Using the equirectangular file to generate the environment texture.')
        # Setting flip_X to False allows us to set the environment texture of the
        # object correctly.
        env_texture = equirectangular_file_to_texture(parameters['equirectangular'], False)
        has_env_texture = True
        if parameters['equirectangular'].suffix.lower() in '.hdr .pic':
            gamma_correct = True
            is_hdr = True
        if parameters['skybox']:
            # Generate a skybox.
            cube_map = equirectangular_file_to_cubemap(parameters['equirectangular'], True)
            has_cube_map = True
    elif 'cubemap' in parameters.keys() and parameters['cubemap']:
        print('Using the cubemap files to generate the environment texture.')
        cube_map = read_cubemap(parameters['cubemap'])
        has_cube_map = True
    else:
        print('An environment texture is required,\n'
              'please add the necessary equiangular'
              ' or cubemap file paths to the json file.')
        return

    # Get the textures
    base_color = read_texture(parameters['albedo'])
    base_color.UseSRGBColorSpaceOn()
    normal = read_texture(parameters['normal'])
    material = read_texture(parameters['material'])
    emissive = read_texture(parameters['emissive'])
    emissive.UseSRGBColorSpaceOn()

    # Get the surface
    surface = parameters['object'].lower()
    available_surfaces = {'boy', 'mobius', 'randomhills', 'torus', 'sphere', 'clippedsphere', 'cube', 'clippedcube'}
    if surface not in available_surfaces:
        surface = 'boy'
    if surface == 'mobius':
        source = get_mobius()
    elif surface == 'randomhills':
        source = get_random_hills()
    elif surface == 'torus':
        source = get_torus()
    elif surface == 'sphere':
        source = get_sphere()
    elif surface == 'clippedsphere':
        source = get_clipped_sphere()
    elif surface == 'cube':
        source = get_cube()
    elif surface == 'clippedcube':
        source = get_clipped_cube()
    else:
        source = get_boy()

    colors = vtkNamedColors()

    # Default background color.
    colors.SetColor('BkgColor', [26, 51, 102, 255])
    colors.SetColor('VTKBlue', [6, 79, 141, 255])
    # Let's make a complementary colour to VTKBlue.
    colors.SetColor('VTKBlueComp', [249, 176, 114, 255])

    # Check for missing parameters.
    if 'bkgcolor' not in parameters.keys():
        parameters['bkgcolor'] = 'BkgColor'
    if 'objcolor' not in parameters.keys():
        parameters['objcolor'] = 'White'
    if 'skybox' not in parameters.keys():
        parameters['skybox'] = False

    # Build the pipeline.
    # ren_1 is for the slider rendering,
    # ren_2 is for the object rendering.
    ren_1 = vtkRenderer()
    ren_2 = vtkOpenGLRenderer()
    render_window = vtkRenderWindow()
    # The order here is important.
    # This ensures that the sliders will be in ren_1.
    render_window.AddRenderer(ren_2)
    render_window.AddRenderer(ren_1)
    ren_1.SetViewport(0.0, 0.0, 0.2, 1.0)
    ren_2.SetViewport(0.2, 0.0, 1, 1)

    interactor = vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)
    style = vtkInteractorStyleTrackballCamera()
    interactor.SetInteractorStyle(style)

    # Set up tone mapping so we can vary the exposure.
    # Custom Passes.
    camera_p = vtkCameraPass()
    seq = vtkSequencePass()
    opaque = vtkOpaquePass()
    lights = vtkLightsPass()
    overlay = vtkOverlayPass()

    passes = vtkRenderPassCollection()
    passes.AddItem(lights)
    passes.AddItem(opaque)
    passes.AddItem(overlay)
    seq.SetPasses(passes)
    camera_p.SetDelegatePass(seq)

    tone_mapping_p = vtkToneMappingPass()
    tone_mapping_p.SetToneMappingType(vtkToneMappingPass().GenericFilmic)
    tone_mapping_p.SetGenericFilmicDefaultPresets()
    tone_mapping_p.SetUseACES(True)
    tone_mapping_p.SetDelegatePass(camera_p)

    ren_2.SetPass(tone_mapping_p)

    # Let's use a nonmetallic surface.
    # Range: [0 ... 1]
    diffuse_coefficient = 1.0
    # Range: [0 ... 1]
    roughness_coefficient = 0.3
    # Range: [0 ... 1]
    metallic_coefficient = 0.0
    # Other parameters.
    # Range: [0 ... 5]
    occlusion_strength = 1.0
    # Range: [0 ... 5]
    normal_scale = 1.0
    # Make VTK silvery in appearance.
    # emissive_col = colors.GetColor3d('VTKBlueComp')
    # emissive_factor = emissive_col
    emissive_factor = [1.0, 1.0, 1.0]

    # Turn off the default lighting and use image based lighting.
    ren_2.AutomaticLightCreationOff()
    ren_2.UseImageBasedLightingOn()
    if has_env_texture:
        if is_hdr:
            ren_2.UseSphericalHarmonicsOn()
            ren_2.SetEnvironmentTexture(env_texture)
        else:
            ren_2.UseSphericalHarmonicsOff()
            ren_2.SetEnvironmentTexture(env_texture)
    else:
        ren_2.UseSphericalHarmonicsOff()
        ren_2.SetEnvironmentTexture(cube_map)
    ren_1.SetBackground(colors.GetColor3d('Snow'))
    ren_2.SetBackground(colors.GetColor3d(parameters['bkgcolor']))

    mapper = vtkPolyDataMapper()
    mapper.SetInputData(source)

    actor = vtkActor()
    actor.SetMapper(mapper)
    # Enable PBR on the model.
    actor.GetProperty().SetInterpolationToPBR()
    # Configure the basic properties.
    actor.GetProperty().SetColor(colors.GetColor3d(parameters['objcolor']))
    actor.GetProperty().SetDiffuse(diffuse_coefficient)
    actor.GetProperty().SetRoughness(roughness_coefficient)
    actor.GetProperty().SetMetallic(metallic_coefficient)
    # Configure textures (needs tcoords on the mesh).
    actor.GetProperty().SetBaseColorTexture(base_color)
    actor.GetProperty().SetORMTexture(material)
    actor.GetProperty().SetOcclusionStrength(occlusion_strength)
    actor.GetProperty().SetEmissiveTexture(emissive)
    actor.GetProperty().SetEmissiveFactor(emissive_factor)
    # Needs tcoords, normals and tangents on the mesh.
    actor.GetProperty().SetNormalTexture(normal)
    actor.GetProperty().SetNormalScale(normal_scale)
    ren_2.AddActor(actor)

    if has_cube_map:
        skybox_actor = vtkSkybox()
        skybox_actor.SetTexture(cube_map)
        if gamma_correct:
            skybox_actor.GammaCorrectOn()
        else:
            skybox_actor.GammaCorrectOff()
        ren_2.AddActor(skybox_actor)

    # Create the slider callbacks to manipulate various parameters.
    step_size = 1.0 / 5
    pos_y = 0.1
    pos_x0 = 0.02
    pos_x1 = 0.18

    sw_p = SliderProperties()
    sw_p.initial_value = 1.0
    sw_p.maximum_value = 5.0
    sw_p.title = 'Exposure'
    # Screen coordinates.
    sw_p.p1 = [pos_x0, pos_y]
    sw_p.p2 = [pos_x1, pos_y]
    pos_y += step_size

    sw_exposure = make_slider_widget(sw_p)
    sw_exposure.SetInteractor(interactor)
    sw_exposure.SetAnimationModeToAnimate()
    sw_exposure.EnabledOn()
    sw_exposure.SetCurrentRenderer(ren_1)
    sw_exposure_cb = SliderCallbackExposure(tone_mapping_p)
    sw_exposure.AddObserver(vtkCommand.InteractionEvent, sw_exposure_cb)

    sw_p.initial_value = metallic_coefficient
    sw_p.maximum_value = 1.0
    sw_p.title = 'Metallicity'
    # Screen coordinates.
    sw_p.p1 = [pos_x0, pos_y]
    sw_p.p2 = [pos_x1, pos_y]
    pos_y += step_size

    sw_metallic = make_slider_widget(sw_p)
    sw_metallic.SetInteractor(interactor)
    sw_metallic.SetAnimationModeToAnimate()
    sw_metallic.EnabledOn()
    sw_metallic.SetCurrentRenderer(ren_1)
    sw_metallic_cb = SliderCallbackMetallic(actor.GetProperty())
    sw_metallic.AddObserver(vtkCommand.InteractionEvent, sw_metallic_cb)

    sw_p.initial_value = roughness_coefficient
    sw_p.title = 'Roughness'
    # Screen coordinates.
    sw_p.p1 = [pos_x0, pos_y]
    sw_p.p2 = [pos_x1, pos_y]
    pos_y += step_size

    sw_roughnesss = make_slider_widget(sw_p)
    sw_roughnesss.SetInteractor(interactor)
    sw_roughnesss.SetAnimationModeToAnimate()
    sw_roughnesss.EnabledOn()
    sw_roughnesss.SetCurrentRenderer(ren_1)
    sw_roughnesss_cb = SliderCallbackRoughness(actor.GetProperty())
    sw_roughnesss.AddObserver(vtkCommand.InteractionEvent, sw_roughnesss_cb)

    sw_p.initial_value = occlusion_strength
    sw_p.maximum_value = 1
    sw_p.title = 'Occlusion'
    # Screen coordinates.
    sw_p.p1 = [pos_x0, pos_y]
    sw_p.p2 = [pos_x1, pos_y]
    pos_y += step_size

    sw_occlusion_strength = make_slider_widget(sw_p)
    sw_occlusion_strength.SetInteractor(interactor)
    sw_occlusion_strength.SetAnimationModeToAnimate()
    sw_occlusion_strength.EnabledOn()
    sw_occlusion_strength.SetCurrentRenderer(ren_1)
    sw_occlusion_strength_cb = SliderCallbackOcclusionStrength(actor.GetProperty())
    sw_occlusion_strength.AddObserver(vtkCommand.InteractionEvent, sw_occlusion_strength_cb)

    sw_p.initial_value = normal_scale
    sw_p.maximum_value = 5
    sw_p.title = 'Normal'
    # Screen coordinates.
    sw_p.p1 = [pos_x0, pos_y]
    sw_p.p2 = [pos_x1, pos_y]
    pos_y += step_size

    sw_normal = make_slider_widget(sw_p)
    sw_normal.SetInteractor(interactor)
    sw_normal.SetAnimationModeToAnimate()
    sw_normal.EnabledOn()
    sw_normal.SetCurrentRenderer(ren_1)
    sw_normal_cb = SliderCallbackNormalScale(actor.GetProperty())
    sw_normal.AddObserver(vtkCommand.InteractionEvent, sw_normal_cb)

    name = Path(sys.argv[0]).stem
    render_window.SetSize(1000, 625)
    render_window.Render()
    render_window.SetWindowName(name)

    if vtk_version_ok(9, 0, 20210718):
        try:
            cam_orient_manipulator = vtkCameraOrientationWidget()
            cam_orient_manipulator.SetParentRenderer(ren_2)
            # Enable the widget.
            cam_orient_manipulator.On()
        except AttributeError:
            pass
    else:
        axes = vtkAxesActor()
        widget = vtkOrientationMarkerWidget()
        rgba = [0.0, 0.0, 0.0, 0.0]
        colors.GetColor("Carrot", rgba)
        widget.SetOutlineColor(rgba[0], rgba[1], rgba[2])
        widget.SetOrientationMarker(axes)
        widget.SetInteractor(interactor)
        widget.SetViewport(0.0, 0.0, 0.2, 0.2)
        widget.EnabledOn()
        widget.InteractiveOn()

    print_callback = PrintCallback(interactor, name, 1, False)
    # print_callback = PrintCallback(interactor, name + '.jpg', 1, False)
    interactor.AddObserver('KeyPressEvent', print_callback)

    interactor.Start()


def vtk_version_ok(major, minor, build):
    """
    Check the VTK version.

    :param major: Major version.
    :param minor: Minor version.
    :param build: Build version.
    :return: True if the requested VTK version is greater or equal to the actual VTK version.
    """
    needed_version = 10000000000 * int(major) + 100000000 * int(minor) + int(build)
    try:
        vtk_version_number = VTK_VERSION_NUMBER
    except AttributeError:  # as error:
        ver = vtkVersion()
        vtk_version_number = 10000000000 * ver.GetVTKMajorVersion() + 100000000 * ver.GetVTKMinorVersion() \
                             + ver.GetVTKBuildVersion()
    if vtk_version_number >= needed_version:
        return True
    else:
        return False


def get_parameters(fn_path, surface_name):
    """
    Read the parameters from a JSON file and check that the file paths exist.


    :param fn_path: The path to the JSON file.
    :param surface_name: The surface name.
    :return: True if the paths correspond to files and the parameters.
    """
    with open(fn_path) as data_file:
        json_data = json.load(data_file)
    parameters = dict()
    paths_ok = True

    # Extract the values.
    allowed_keys_no_paths = {'object', 'objcolor', 'bkgcolor', 'skybox'}
    allowed_keys_paths = {'cubemap', 'equirectangular',
                          'albedo', 'normal', 'material',
                          'coat', 'anisotropy', 'emissive'}

    for k, v in json_data.items():
        if k in allowed_keys_no_paths:
            parameters[k] = v
            continue
        if k in allowed_keys_paths:
            if k == 'cubemap':
                cm = list()
                if len(v) != 6:
                    print('There must be six filenames for the cubemap.')
                    paths_ok = False
                else:
                    for idx in range(len(v)):
                        if idx == 3:
                            pass
                        if v[idx]:
                            cm.append(fn_path.parent / v[idx])
                            if not cm[-1].is_file():
                                paths_ok = False
                                print('Not a file:', cm[idx])
                        else:
                            print('A missing path in the cubemap.')
                            paths_ok = False
                parameters[k] = cm
            else:
                if v:
                    parameters[k] = fn_path.parent / v
                    if not (parameters[k].is_file() or parameters[k].is_dir()):
                        print('Not a file or path:', parameters[k])
                        paths_ok = False
                else:
                    print('No path for the key', k)
                    paths_ok = False

    # Set the surface, if required.
    if ('object' in parameters.keys() and not parameters['object']) or 'object' not in parameters.keys():
        parameters['object'] = 'Boy'
    if surface_name:
        parameters['object'] = surface_name

    return paths_ok, parameters


def display_parameters(parameters):
    res = list()
    parameter_keys = ["object", "objcolor", "bkgcolor", "skybox", "cubemap", "equirectangular", "albedo", "normal",
                      "material", "coat", "anisotropy", "emissive"]
    for k in parameter_keys:
        if k != 'cubemap':
            if k in parameters:
                res.append(f'{k:15}: {parameters[k]}')
        else:
            if k in parameters:
                for idx in range(len(parameters[k])):
                    if idx == 0:
                        res.append(f'{k:15}: {parameters[k][idx]}')
                    else:
                        res.append(f'{" " * 17}{parameters[k][idx]}')
    return res


def equirectangular_file_to_texture(fn_path, flip_x=False):
    """
    Read an equirectangular environment file and convert to a texture.

    :param fn_path: The equirectangular file path.
    :param flip_x: Flip x-axis of the texture.
    :return: The texture.
    """
    texture = vtkTexture()

    suffix = fn_path.suffix.lower()
    if suffix in ['.jpeg', '.jpg', '.png']:
        reader_factory = vtkImageReader2Factory()
        img_reader = reader_factory.CreateImageReader2(str(fn_path))
        img_reader.SetFileName(str(fn_path))

        if flip_x:
            flip = vtkImageFlip()
            flip.SetInputConnection(img_reader.GetOutputPort(0))
            flip.SetFilteredAxis(0)  # flip x axis
            texture.SetInputConnection(flip.GetOutputPort())
        else:
            texture.SetInputConnection(img_reader.GetOutputPort(0))

    else:
        reader = vtkHDRReader()
        extensions = reader.GetFileExtensions()
        # Check the image can be read.
        if not reader.CanReadFile(str(fn_path)):
            print('CanReadFile failed for ', fn_path)
            return None
        if suffix not in extensions:
            print('Unable to read this file extension: ', suffix)
            return None
        reader.SetFileName(str(fn_path))

        if flip_x:
            flip = vtkImageFlip()
            flip.SetInputConnection(reader.GetOutputPort())
            flip.SetFilteredAxis(0)  # flip x axis
            texture.SetInputConnection(flip.GetOutputPort())
        else:
            texture.SetInputConnection(reader.GetOutputPort())
        texture.SetColorModeToDirectScalars()

    texture.MipmapOn()
    texture.InterpolateOn()

    return texture


def equirectangular_file_to_cubemap(fn_path, flip_x=False):
    """
    Read an equirectangular environment file and convert to a cubemap.

    :param fn_path: The equirectangular file path.
    :param flip_x: Flip x-axis of the texture.
    :return: The cubemap texture.
    """
    env_texture = equirectangular_file_to_texture(fn_path, flip_x)
    cube_map = vtkEquirectangularToCubeMapTexture()
    cube_map.SetInputTexture(env_texture)
    cube_map.MipmapOn()
    cube_map.InterpolateOn()

    return cube_map


def read_cubemap(cubemap):
    """
    Read six images forming a cubemap.

    :param cubemap: The paths to the six cubemap files.
    :return: The cubemap texture.
    """
    cube_map = vtkTexture()
    cube_map.CubeMapOn()

    i = 0
    for fn in cubemap:
        # Read the images.
        reader_factory = vtkImageReader2Factory()
        img_reader = reader_factory.CreateImageReader2(str(fn))
        img_reader.SetFileName(str(fn))

        # Each image must be flipped in Y due to canvas
        #  versus vtk ordering.
        flip = vtkImageFlip()
        flip.SetInputConnection(img_reader.GetOutputPort(0))
        flip.SetFilteredAxis(1)  # flip y axis
        cube_map.SetInputConnection(i, flip.GetOutputPort())
        i += 1

    cube_map.MipmapOn()
    cube_map.InterpolateOn()

    return cube_map


def read_texture(image_path):
    """
    Read an image and convert it to a texture
    :param image_path: The image path.
    :return: The texture.
    """

    suffix = image_path.suffix.lower()
    valid_extensions = ['.jpg', '.png', '.bmp', '.tiff', '.pnm', '.pgm', '.ppm']
    if suffix not in valid_extensions:
        print('Unable to read the texture file (wrong extension):', image_path)
        return None

    # Read the images
    reader_factory = vtkImageReader2Factory()
    img_reader = reader_factory.CreateImageReader2(str(image_path))
    img_reader.SetFileName(str(image_path))

    texture = vtkTexture()
    texture.InterpolateOn()
    texture.SetInputConnection(img_reader.GetOutputPort(0))
    texture.Update()

    return texture


def check_for_missing_textures(parameters, wanted_textures):
    """
    Check that the needed textures exist.

    :param parameters: The parameters.
    :param wanted_textures: The wanted textures.
    :return: True if all the wanted textures are present.
    """
    have_textures = True
    for texture_name in wanted_textures:
        if texture_name not in parameters:
            print('Missing texture:', texture_name)
            have_textures = False
        elif not parameters[texture_name]:
            print('No texture path for:', texture_name)
            have_textures = False

    return have_textures


def get_boy():
    u_resolution = 51
    v_resolution = 51
    surface = vtkParametricBoy()

    source = vtkParametricFunctionSource()
    source.SetUResolution(u_resolution)
    source.SetVResolution(v_resolution)
    source.GenerateTextureCoordinatesOn()
    source.SetParametricFunction(surface)
    source.Update()

    # Build the tangents
    tangents = vtkPolyDataTangents()
    tangents.SetInputConnection(source.GetOutputPort())
    tangents.Update()
    return tangents.GetOutput()


def get_mobius():
    u_resolution = 51
    v_resolution = 51
    surface = vtkParametricMobius()
    surface.SetMinimumV(-0.25)
    surface.SetMaximumV(0.25)

    source = vtkParametricFunctionSource()
    source.SetUResolution(u_resolution)
    source.SetVResolution(v_resolution)
    source.GenerateTextureCoordinatesOn()
    source.SetParametricFunction(surface)
    source.Update()

    # Build the tangents
    tangents = vtkPolyDataTangents()
    tangents.SetInputConnection(source.GetOutputPort())
    tangents.Update()

    transform = vtkTransform()
    transform.RotateX(-90.0)
    transform_filter = vtkTransformPolyDataFilter()
    transform_filter.SetInputConnection(tangents.GetOutputPort())
    transform_filter.SetTransform(transform)
    transform_filter.Update()

    return transform_filter.GetOutput()


def get_random_hills():
    u_resolution = 51
    v_resolution = 51
    surface = vtkParametricRandomHills()
    surface.SetRandomSeed(1)
    surface.SetNumberOfHills(30)
    # If you want a plane
    # surface.SetHillAmplitude(0)

    source = vtkParametricFunctionSource()
    source.SetUResolution(u_resolution)
    source.SetVResolution(v_resolution)
    source.GenerateTextureCoordinatesOn()
    source.SetParametricFunction(surface)
    source.Update()

    # Build the tangents
    tangents = vtkPolyDataTangents()
    tangents.SetInputConnection(source.GetOutputPort())
    tangents.Update()

    transform = vtkTransform()
    transform.Translate(0.0, 5.0, 15.0)
    transform.RotateX(-90.0)
    transform_filter = vtkTransformPolyDataFilter()
    transform_filter.SetInputConnection(tangents.GetOutputPort())
    transform_filter.SetTransform(transform)
    transform_filter.Update()

    return transform_filter.GetOutput()


def get_torus():
    u_resolution = 51
    v_resolution = 51
    surface = vtkParametricTorus()

    source = vtkParametricFunctionSource()
    source.SetUResolution(u_resolution)
    source.SetVResolution(v_resolution)
    source.GenerateTextureCoordinatesOn()
    source.SetParametricFunction(surface)
    source.Update()

    # Build the tangents
    tangents = vtkPolyDataTangents()
    tangents.SetInputConnection(source.GetOutputPort())
    tangents.Update()

    transform = vtkTransform()
    transform.RotateX(-90.0)
    transform_filter = vtkTransformPolyDataFilter()
    transform_filter.SetInputConnection(tangents.GetOutputPort())
    transform_filter.SetTransform(transform)
    transform_filter.Update()

    return transform_filter.GetOutput()


def get_sphere():
    theta_resolution = 32
    phi_resolution = 32
    surface = vtkTexturedSphereSource()
    surface.SetThetaResolution(theta_resolution)
    surface.SetPhiResolution(phi_resolution)

    # Now the tangents.
    tangents = vtkPolyDataTangents()
    tangents.SetInputConnection(surface.GetOutputPort())
    tangents.Update()
    return tangents.GetOutput()


def get_clipped_sphere():
    theta_resolution = 32
    phi_resolution = 32
    surface = vtkTexturedSphereSource()
    surface.SetThetaResolution(theta_resolution)
    surface.SetPhiResolution(phi_resolution)

    clip_plane = vtkPlane()
    clip_plane.SetOrigin(0, 0.3, 0)
    clip_plane.SetNormal(0, -1, 0)

    clipper = vtkClipPolyData()
    clipper.SetInputConnection(surface.GetOutputPort())
    clipper.SetClipFunction(clip_plane)
    clipper.GenerateClippedOutputOn()

    # Now the tangents.
    tangents = vtkPolyDataTangents()
    tangents.SetInputConnection(clipper.GetOutputPort())
    tangents.Update()
    return tangents.GetOutput()


def get_cube():
    surface = vtkCubeSource()

    # Triangulate.
    triangulation = vtkTriangleFilter()
    triangulation.SetInputConnection(surface.GetOutputPort())

    # Subdivide the triangles
    subdivide = vtkLinearSubdivisionFilter()
    subdivide.SetInputConnection(triangulation.GetOutputPort())
    subdivide.SetNumberOfSubdivisions(3)

    # Now the tangents.
    tangents = vtkPolyDataTangents()
    tangents.SetInputConnection(subdivide.GetOutputPort())
    tangents.Update()
    return tangents.GetOutput()


def get_clipped_cube():
    surface = vtkCubeSource()

    # Triangulate.
    triangulation = vtkTriangleFilter()
    triangulation.SetInputConnection(surface.GetOutputPort())

    # Subdivide the triangles
    subdivide = vtkLinearSubdivisionFilter()
    subdivide.SetInputConnection(triangulation.GetOutputPort())
    subdivide.SetNumberOfSubdivisions(5)

    clip_plane = vtkPlane()
    clip_plane.SetOrigin(0, 0.3, 0)
    clip_plane.SetNormal(0, -1, -1)

    clipper = vtkClipPolyData()
    clipper.SetInputConnection(subdivide.GetOutputPort())
    clipper.SetClipFunction(clip_plane)
    clipper.GenerateClippedOutputOn()

    cleaner = vtkCleanPolyData()
    cleaner.SetInputConnection(clipper.GetOutputPort())
    cleaner.SetTolerance(0.005)
    cleaner.Update()

    normals = vtkPolyDataNormals()
    normals.SetInputConnection(cleaner.GetOutputPort())
    normals.FlipNormalsOn()
    normals.SetFeatureAngle(60)

    # Now the tangents.
    tangents = vtkPolyDataTangents()
    tangents.SetInputConnection(normals.GetOutputPort())
    tangents.ComputeCellTangentsOn()
    tangents.ComputePointTangentsOff()
    tangents.Update()
    return tangents.GetOutput()


def uv_tcoords(u_resolution, v_resolution, pd):
    """
    Generate u, v texture coordinates on a parametric surface.
    :param u_resolution: u resolution
    :param v_resolution: v resolution
    :param pd: The polydata representing the surface.
    :return: The polydata with the texture coordinates added.
    """
    u0 = 1.0
    v0 = 0.0
    du = 1.0 / (u_resolution - 1)
    dv = 1.0 / (v_resolution - 1)
    num_pts = pd.GetNumberOfPoints()
    t_coords = vtkFloatArray()
    t_coords.SetNumberOfComponents(2)
    t_coords.SetNumberOfTuples(num_pts)
    t_coords.SetName('Texture Coordinates')
    pt_id = 0
    u = u0
    for i in range(0, u_resolution):
        v = v0
        for j in range(0, v_resolution):
            tc = [u, v]
            t_coords.SetTuple(pt_id, tc)
            v += dv
            pt_id += 1
        u -= du
    pd.GetPointData().SetTCoords(t_coords)
    return pd


class SliderProperties:
    tube_width = 0.008
    slider_length = 0.075
    slider_width = 0.025
    end_cap_length = 0.025
    end_cap_width = 0.025
    title_height = 0.025
    label_height = 0.020

    minimum_value = 0.0
    maximum_value = 1.0
    initial_value = 0.0

    p1 = [0.02, 0.1]
    p2 = [0.18, 0.1]

    title = None

    title_color = 'Black'
    label_color = 'Black'
    value_color = 'DarkSlateGray'
    slider_color = 'BurlyWood'
    selected_color = 'Lime'
    bar_color = 'Black'
    bar_ends_color = 'Indigo'


def make_slider_widget(properties):
    colors = vtkNamedColors()

    slider = vtkSliderRepresentation2D()

    slider.SetMinimumValue(properties.minimum_value)
    slider.SetMaximumValue(properties.maximum_value)
    slider.SetValue(properties.initial_value)
    slider.SetTitleText(properties.title)

    slider.GetPoint1Coordinate().SetCoordinateSystemToNormalizedDisplay()
    slider.GetPoint1Coordinate().SetValue(properties.p1[0], properties.p1[1])
    slider.GetPoint2Coordinate().SetCoordinateSystemToNormalizedDisplay()
    slider.GetPoint2Coordinate().SetValue(properties.p2[0], properties.p2[1])

    slider.SetTubeWidth(properties.tube_width)
    slider.SetSliderLength(properties.slider_length)
    slider.SetSliderWidth(properties.slider_width)
    slider.SetEndCapLength(properties.end_cap_length)
    slider.SetEndCapWidth(properties.end_cap_width)
    slider.SetTitleHeight(properties.title_height)
    slider.SetLabelHeight(properties.label_height)

    # Set the color properties
    # Change the color of the title.
    slider.GetTitleProperty().SetColor(colors.GetColor3d(properties.title_color))
    # Change the color of the label.
    slider.GetTitleProperty().SetColor(colors.GetColor3d(properties.label_color))
    # Change the color of the bar.
    slider.GetTubeProperty().SetColor(colors.GetColor3d(properties.bar_color))
    # Change the color of the ends of the bar.
    slider.GetCapProperty().SetColor(colors.GetColor3d(properties.bar_ends_color))
    # Change the color of the knob that slides.
    slider.GetSliderProperty().SetColor(colors.GetColor3d(properties.slider_color))
    # Change the color of the knob when the mouse is held on it.
    slider.GetSelectedProperty().SetColor(colors.GetColor3d(properties.selected_color))
    # Change the color of the text displaying the value.
    slider.GetLabelProperty().SetColor(colors.GetColor3d(properties.value_color))

    slider_widget = vtkSliderWidget()
    slider_widget.SetRepresentation(slider)

    return slider_widget


class SliderCallbackExposure:
    def __init__(self, tone_mapping_property):
        self.tone_mapping_property = tone_mapping_property

    def __call__(self, caller, ev):
        slider_widget = caller
        value = slider_widget.GetRepresentation().GetValue()
        self.tone_mapping_property.SetExposure(value)


class SliderCallbackMetallic:
    def __init__(self, actor_property):
        self.actor_property = actor_property

    def __call__(self, caller, ev):
        slider_widget = caller
        value = slider_widget.GetRepresentation().GetValue()
        self.actor_property.SetMetallic(value)


class SliderCallbackRoughness:
    def __init__(self, actor_property):
        self.actorProperty = actor_property

    def __call__(self, caller, ev):
        slider_widget = caller
        value = slider_widget.GetRepresentation().GetValue()
        self.actorProperty.SetRoughness(value)


class SliderCallbackOcclusionStrength:
    def __init__(self, actor_property):
        self.actorProperty = actor_property

    def __call__(self, caller, ev):
        slider_widget = caller
        value = slider_widget.GetRepresentation().GetValue()
        self.actorProperty.SetOcclusionStrength(value)


class SliderCallbackNormalScale:
    def __init__(self, actor_property):
        self.actorProperty = actor_property

    def __call__(self, caller, ev):
        slider_widget = caller
        value = slider_widget.GetRepresentation().GetValue()
        self.actorProperty.SetNormalScale(value)


class PrintCallback:
    def __init__(self, caller, file_name, image_quality=1, rgba=True):
        """
        Set the parameters for writing the
         render window view to an image file.

        :param caller: The caller for the callback.
        :param file_name: The image file name.
        :param image_quality: The image quality.
        :param rgba: The buffer type, (if true, there is no background in the screenshot).
        """
        self.caller = caller
        self.image_quality = image_quality
        self.rgba = rgba
        if not file_name:
            self.path = None
            print("A file name is required.")
            return
        pth = Path(file_name).absolute()
        valid_suffixes = ['.jpeg', '.jpg', '.png']
        if pth.suffix:
            ext = pth.suffix.lower()
        else:
            ext = '.png'
        if ext not in valid_suffixes:
            ext = '.png'
        self.suffix = ext
        self.path = Path(str(pth)).with_suffix(ext)

    def __call__(self, caller, ev):
        if not self.path:
            print("A file name is required.")
            return
        # Save the screenshot.
        if caller.GetKeyCode() == "k":
            w2if = vtkWindowToImageFilter()
            w2if.SetInput(caller.GetRenderWindow())
            w2if.SetScale(self.image_quality, self.image_quality)
            if self.rgba:
                w2if.SetInputBufferTypeToRGBA()
            else:
                w2if.SetInputBufferTypeToRGB()
            # Read from the front buffer.
            w2if.ReadFrontBufferOn()
            w2if.Update()
            if self.suffix in ['.jpeg', '.jpg']:
                writer = vtkJPEGWriter()
            else:
                writer = vtkPNGWriter()
            writer.SetFileName(self.path)
            writer.SetInputData(w2if.GetOutput())
            writer.Write()
            print('Screenshot saved to:', self.path)


if __name__ == '__main__':
    main()
