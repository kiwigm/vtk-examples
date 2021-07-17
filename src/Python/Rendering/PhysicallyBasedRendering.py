#!/usr/bin/env python

from pathlib import Path
from pathlib import PurePath

import vtk


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
    parser.add_argument('path', help='The path to the cubemap files e.g. skyboxes/skybox2/')
    parser.add_argument('material_fn', help='The path to the material texture file e.g. vtk_Material.png')
    parser.add_argument('albedo_fn', help='The path to the albedo (base colour) texture file e.g. vtk_Base_Color.png')
    parser.add_argument('normal_fn', help='The path to the normal texture file e.g. vtk_Normal.png')
    parser.add_argument('emissive_fn', help='The path to the emissive texture file e.g. vtk_dark_bkg.png')
    parser.add_argument('surface', nargs='?', default='Boy', help="The surface to use. Boy's surface is the default.")
    args = parser.parse_args()
    return args.path, args.material_fn, args.albedo_fn, args.normal_fn, args.emissive_fn, args.surface


def main():
    if not vtk_version_ok(8, 90, 0):
        print('You need VTK version 8.90 or greater to run this program.')
        return
    path, material_fn, albedo_fn, normal_fn, emissive_fn, surface = get_program_parameters()
    cube_path = Path(path)
    if not cube_path.is_dir():
        print('This path does not exist:', cube_path)
        return

    # A dictionary of the skybox folder name and the skybox files in it.
    skybox_files = {
        'skybox0':
            ['right.jpg', 'left.jpg', 'top.jpg', 'bottom.jpg', 'front.jpg',
             'back.jpg'],
        'skybox1':
            ['skybox-px.jpg', 'skybox-nx.jpg', 'skybox-py.jpg', 'skybox-ny.jpg',
             'skybox-pz.jpg', 'skybox-nz.jpg'],
        'skybox2':
            ['posx.jpg', 'negx.jpg', 'posy.jpg', 'negy.jpg', 'posz.jpg',
             'negz.jpg']}

    # Load the cube map
    cubemap = read_cube_map(cube_path, skybox_files[PurePath(cube_path).name])

    # Load the skybox
    # Read it again as there is no deep copy for vtkTexture
    skybox = read_cube_map(cube_path, skybox_files[PurePath(cube_path).name])
    skybox.InterpolateOn()
    skybox.RepeatOff()
    skybox.EdgeClampOn()

    # Get the textures
    material = get_texture(material_fn)
    albedo = get_texture(albedo_fn)
    albedo.UseSRGBColorSpaceOn()
    normal = get_texture(normal_fn)
    emissive = get_texture(emissive_fn)
    emissive.UseSRGBColorSpaceOn()

    # Get the surface
    surface = surface.lower()
    available_surfaces = {'boy', 'mobius', 'randomhills', 'torus', 'sphere', 'cube'}
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
    elif surface == 'cube':
        source = get_cube()
    else:
        source = get_boy()

    colors = vtk.vtkNamedColors()

    # Set the background color.
    colors.SetColor('BkgColor', [26, 51, 102, 255])
    colors.SetColor('VTKBlue', [6, 79, 141, 255])
    # Let's make a complementary colour to VTKBlue
    colors.SetColor('VTKBlueComp', [249, 176, 114, 255])

    renderer = vtk.vtkOpenGLRenderer()
    render_window = vtk.vtkRenderWindow()
    render_window.AddRenderer(renderer)
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(render_window)

    # Lets use a rough metallic surface
    metallic_coefficient = 1.0
    roughness_coefficient = 0.8
    # Other parameters
    occlusion_strength = 10.0
    normal_scale = 10.0
    emissive_col = colors.GetColor3d('VTKBlueComp')
    emissive_factor = emissive_col
    # emissive_factor = [1.0, 1.0, 1.0]

    slw_p = SliderProperties()
    slw_p.initial_value = metallic_coefficient
    slw_p.title = 'Metallicity'

    slider_widget_metallic = make_slider_widget(slw_p)
    slider_widget_metallic.SetInteractor(interactor)
    slider_widget_metallic.SetAnimationModeToAnimate()
    slider_widget_metallic.EnabledOn()

    slw_p.initial_value = roughness_coefficient
    slw_p.title = 'Roughness'
    slw_p.p1 = [0.2, 0.9]
    slw_p.p2 = [0.8, 0.9]

    slider_widget_roughness = make_slider_widget(slw_p)
    slider_widget_roughness.SetInteractor(interactor)
    slider_widget_roughness.SetAnimationModeToAnimate()
    slider_widget_roughness.EnabledOn()

    slw_p.initial_value = occlusion_strength
    slw_p.maximum_value = occlusion_strength
    slw_p.title = 'Occlusion'
    slw_p.p1 = [0.1, 0.1]
    slw_p.p2 = [0.1, 0.9]

    slider_widget_occlusion_strength = make_slider_widget(slw_p)
    slider_widget_occlusion_strength.SetInteractor(interactor)
    slider_widget_occlusion_strength.SetAnimationModeToAnimate()
    slider_widget_occlusion_strength.EnabledOn()

    slw_p.initial_value = normal_scale
    slw_p.maximum_value = normal_scale
    slw_p.title = 'Normal'
    slw_p.p1 = [0.85, 0.1]
    slw_p.p2 = [0.85, 0.9]

    slider_widget_normal = make_slider_widget(slw_p)
    slider_widget_normal.SetInteractor(interactor)
    slider_widget_normal.SetAnimationModeToAnimate()
    slider_widget_normal.EnabledOn()

    # Build the pipeline
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(source)

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    actor.GetProperty().SetInterpolationToPBR()

    # configure the basic properties
    actor.GetProperty().SetColor(colors.GetColor3d('White'))
    actor.GetProperty().SetMetallic(metallic_coefficient)
    actor.GetProperty().SetRoughness(roughness_coefficient)

    # configure textures (needs tcoords on the mesh)
    actor.GetProperty().SetBaseColorTexture(albedo)
    actor.GetProperty().SetORMTexture(material)
    actor.GetProperty().SetOcclusionStrength(occlusion_strength)

    actor.GetProperty().SetEmissiveTexture(emissive)
    actor.GetProperty().SetEmissiveFactor(emissive_factor)

    # needs tcoords, normals and tangents on the mesh
    actor.GetProperty().SetNormalTexture(normal)
    actor.GetProperty().SetNormalScale(normal_scale)

    renderer.UseImageBasedLightingOn()
    if vtk_version_ok(9, 0, 0):
        renderer.SetEnvironmentTexture(cubemap)
    else:
        renderer.SetEnvironmentCubeMap(cubemap)
    renderer.SetBackground(colors.GetColor3d('BkgColor'))
    renderer.AddActor(actor)

    # Comment out if you don't want a skybox
    skybox_actor = vtk.vtkSkybox()
    skybox_actor.SetTexture(skybox)
    renderer.AddActor(skybox_actor)

    renderer.UseSphericalHarmonicsOff()

    # Create the slider callbacks to manipulate metallicity, roughness
    # occlusion strength and normal scaling
    slider_widget_metallic.AddObserver(vtk.vtkCommand.InteractionEvent, SliderCallbackMetallic(actor.GetProperty()))
    slider_widget_roughness.AddObserver(vtk.vtkCommand.InteractionEvent, SliderCallbackRoughness(actor.GetProperty()))
    slider_widget_occlusion_strength.AddObserver(vtk.vtkCommand.InteractionEvent,
                                                 SliderCallbackOcclusionStrength(actor.GetProperty()))
    slider_widget_normal.AddObserver(vtk.vtkCommand.InteractionEvent, SliderCallbackNormalScale(actor.GetProperty()))

    render_window.SetSize(640, 480)
    render_window.Render()
    render_window.SetWindowName('PhysicallyBasedRendering')

    axes = vtk.vtkAxesActor()

    widget = vtk.vtkOrientationMarkerWidget()
    rgba = [0.0, 0.0, 0.0, 0.0]
    colors.GetColor('Carrot', rgba)
    widget.SetOutlineColor(rgba[0], rgba[1], rgba[2])
    widget.SetOrientationMarker(axes)
    widget.SetInteractor(interactor)
    widget.SetViewport(0.0, 0.0, 0.2, 0.2)
    widget.SetEnabled(1)
    widget.InteractiveOn()

    interactor.SetRenderWindow(render_window)
    interactor.Initialize()

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
        vtk_version_number = vtk.VTK_VERSION_NUMBER
    except AttributeError:  # as error:
        ver = vtk.vtkVersion()
        vtk_version_number = 10000000000 * ver.GetVTKMajorVersion() + 100000000 * ver.GetVTKMinorVersion() \
                             + ver.GetVTKBuildVersion()
    if vtk_version_number >= needed_version:
        return True
    else:
        return False


def read_cube_map(folder_root, file_names):
    """
    Read the cube map.
    :param folder_root: The folder where the cube maps are stored.
    :param file_names: The names of the cubemap files.
    :return: The cubemap texture.
    """
    texture = vtk.vtkTexture()
    texture.CubeMapOn()
    # Build the file names.
    fns = list()
    for fn in file_names:
        fns.append(folder_root.joinpath(fn))
        if not fns[-1].is_file():
            print('Nonexistent texture file:', fns[-1])
            return None
    i = 0
    for fn in fns:
        # Read the images
        reader_factory = vtk.vtkImageReader2Factory()
        img_reader = reader_factory.CreateImageReader2(str(fn))
        img_reader.SetFileName(str(fn))

        flip = vtk.vtkImageFlip()
        flip.SetInputConnection(img_reader.GetOutputPort())
        flip.SetFilteredAxis(1)  # flip y axis
        texture.SetInputConnection(i, flip.GetOutputPort(0))
        i += 1
    texture.MipmapOn()
    texture.InterpolateOn()
    return texture


def get_texture(image_path):
    """
    Read an image and convert it to a texture
    :param image_path: The image path.
    :return: The texture.
    """
    # Read the image which will be the texture
    path = Path(image_path)
    if not path.is_file():
        print('Nonexistent texture file:', path)
        return None
    extension = path.suffix.lower()
    valid_extensions = ['.jpg', '.png', '.bmp', '.tiff', '.pnm', '.pgm', '.ppm']
    if extension not in valid_extensions:
        print('Unable to read the texture file (wrong extension):', path)
        return None
    texture = vtk.vtkTexture()
    # Read the images
    reader_factory = vtk.vtkImageReader2Factory()
    img_reader = reader_factory.CreateImageReader2(str(path))
    img_reader.SetFileName(str(path))

    texture.SetInputConnection(img_reader.GetOutputPort())
    texture.Update()

    return texture


def get_boy():
    u_resolution = 51
    v_resolution = 51
    surface = vtk.vtkParametricBoy()

    source = vtk.vtkParametricFunctionSource()
    source.SetUResolution(u_resolution)
    source.SetVResolution(v_resolution)
    source.GenerateTextureCoordinatesOn()
    source.SetParametricFunction(surface)
    source.Update()

    # Build the tangents
    tangents = vtk.vtkPolyDataTangents()
    tangents.SetInputConnection(source.GetOutputPort())
    tangents.Update()
    return tangents.GetOutput()


def get_mobius():
    u_resolution = 51
    v_resolution = 51
    surface = vtk.vtkParametricMobius()
    surface.SetMinimumV(-0.25)
    surface.SetMaximumV(0.25)

    source = vtk.vtkParametricFunctionSource()
    source.SetUResolution(u_resolution)
    source.SetVResolution(v_resolution)
    source.GenerateTextureCoordinatesOn()
    source.SetParametricFunction(surface)
    source.Update()

    # Build the tangents
    tangents = vtk.vtkPolyDataTangents()
    tangents.SetInputConnection(source.GetOutputPort())
    tangents.Update()

    transform = vtk.vtkTransform()
    transform.RotateX(90.0)
    transform_filter = vtk.vtkTransformPolyDataFilter()
    transform_filter.SetInputConnection(tangents.GetOutputPort())
    transform_filter.SetTransform(transform)
    transform_filter.Update()

    return transform_filter.GetOutput()


def get_random_hills():
    u_resolution = 51
    v_resolution = 51
    surface = vtk.vtkParametricRandomHills()
    surface.SetRandomSeed(1)
    surface.SetNumberOfHills(30)
    # If you want a plane
    # surface.SetHillAmplitude(0)

    source = vtk.vtkParametricFunctionSource()
    source.SetUResolution(u_resolution)
    source.SetVResolution(v_resolution)
    source.GenerateTextureCoordinatesOn()
    source.SetParametricFunction(surface)
    source.Update()

    # Build the tangents
    tangents = vtk.vtkPolyDataTangents()
    tangents.SetInputConnection(source.GetOutputPort())
    tangents.Update()

    transform = vtk.vtkTransform()
    transform.RotateZ(180.0)
    transform.RotateX(90.0)
    transform_filter = vtk.vtkTransformPolyDataFilter()
    transform_filter.SetInputConnection(tangents.GetOutputPort())
    transform_filter.SetTransform(transform)
    transform_filter.Update()

    return transform_filter.GetOutput()


def get_torus():
    u_resolution = 51
    v_resolution = 51
    surface = vtk.vtkParametricTorus()

    source = vtk.vtkParametricFunctionSource()
    source.SetUResolution(u_resolution)
    source.SetVResolution(v_resolution)
    source.GenerateTextureCoordinatesOn()
    source.SetParametricFunction(surface)
    source.Update()

    # Build the tangents
    tangents = vtk.vtkPolyDataTangents()
    tangents.SetInputConnection(source.GetOutputPort())
    tangents.Update()

    transform = vtk.vtkTransform()
    transform.RotateX(90.0)
    transform_filter = vtk.vtkTransformPolyDataFilter()
    transform_filter.SetInputConnection(tangents.GetOutputPort())
    transform_filter.SetTransform(transform)
    transform_filter.Update()

    return transform_filter.GetOutput()


def get_sphere():
    theta_resolution = 32
    phi_resolution = 32
    surface = vtk.vtkTexturedSphereSource()
    surface.SetThetaResolution(theta_resolution)
    surface.SetPhiResolution(phi_resolution)

    # Now the tangents
    tangents = vtk.vtkPolyDataTangents()
    tangents.SetInputConnection(surface.GetOutputPort())
    tangents.Update()
    return tangents.GetOutput()


def get_cube():
    surface = vtk.vtkCubeSource()

    # Triangulate
    triangulation = vtk.vtkTriangleFilter()
    triangulation.SetInputConnection(surface.GetOutputPort())
    # Subdivide the triangles
    subdivide = vtk.vtkLinearSubdivisionFilter()
    subdivide.SetInputConnection(triangulation.GetOutputPort())
    subdivide.SetNumberOfSubdivisions(3)
    # Now the tangents
    tangents = vtk.vtkPolyDataTangents()
    tangents.SetInputConnection(subdivide.GetOutputPort())
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
    t_coords = vtk.vtkFloatArray()
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


def make_slider_widget(properties):
    colors = vtk.vtkNamedColors()

    slider = vtk.vtkSliderRepresentation2D()

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
    slider.SetTitleHeight(properties.title_height)
    slider.SetLabelHeight(properties.label_height)

    # Set the color properties
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

    slider_widget = vtk.vtkSliderWidget()
    slider_widget.SetRepresentation(slider)

    return slider_widget


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


class SliderProperties:
    tube_width = 0.008
    slider_length = 0.008
    title_height = 0.025
    label_height = 0.025

    minimum_value = 0.0
    maximum_value = 1.0
    initial_value = 1.0

    p1 = [0.2, 0.1]
    p2 = [0.8, 0.1]

    title = None

    title_color = 'MistyRose'
    value_color = 'Cyan'
    slider_color = 'Coral'
    selected_color = 'Lime'
    bar_color = 'PeachPuff'
    bar_ends_color = 'Thistle'

if __name__ == '__main__':
    main()
